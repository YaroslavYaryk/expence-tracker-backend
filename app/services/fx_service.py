from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple, Optional

import httpx
from httpx import HTTPStatusError, RequestError

NBU_EXCHANGE_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"


@dataclass(frozen=True)
class FxRate:
    base: str
    quote: str
    rate: float
    as_of: date


class FxService:
    def __init__(self) -> None:
        # cache: (as_of_date, base, quote) -> (rate, expires_at)
        self.NBU_TABLE_URL = 'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange'
        self._cache: Dict[Tuple[date, str, str], Tuple[float, datetime]] = {}
        # cache for daily NBU table: (as_of_date) -> (uah_per_1_map, resolved_date, expires_at)
        self._day_cache: Dict[date, Tuple[Dict[str, float], date, datetime]] = {}

    def _cache_get(self, key: Tuple[date, str, str]) -> Optional[float]:
        val = self._cache.get(key)
        if not val:
            return None
        rate, expires_at = val
        if datetime.utcnow() >= expires_at:
            self._cache.pop(key, None)
            return None
        return rate

    def _cache_set(self, key: Tuple[date, str, str], rate: float, ttl_seconds: int) -> None:
        self._cache[key] = (rate, datetime.utcnow() + timedelta(seconds=ttl_seconds))

    def _day_cache_get(self, as_of: date) -> Optional[Tuple[Dict[str, float], date]]:
        val = self._day_cache.get(as_of)
        if not val:
            return None
        rates_map, resolved_date, expires_at = val
        if datetime.utcnow() >= expires_at:
            self._day_cache.pop(as_of, None)
            return None
        return rates_map, resolved_date

    def _day_cache_set(self, as_of: date, rates_map: Dict[str, float], resolved_date: date, ttl_seconds: int) -> None:
        self._day_cache[as_of] = (rates_map, resolved_date, datetime.utcnow() + timedelta(seconds=ttl_seconds))

    @staticmethod
    def _ymd_compact(d: date) -> str:
        return d.strftime("%Y%m%d")

    async def _fetch_nbu_table_for_date(self, d: date) -> Dict[str, float]:
        """
        Returns currency -> UAH per 1 unit for given date.
        Always includes UAH=1.0.
        Raises on network/HTTP/parse errors.
        """

        url = f'{self.NBU_TABLE_URL}?date={d.strftime("%Y%m%d")}&json'
        headers = {'Accept': 'application/json'}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url, headers=headers)

                # Перевіряємо статус ПЕРЕД тим як щось робити з тілом відповіді
                r.raise_for_status()
                data = r.json()

        except HTTPStatusError as e:
            print(f"Сервер повернув помилку {e.response.status_code}: {e.response.text}")
        except RequestError as e:
            print(f"Помилка мережі при запиті до {e.request.url}")
        except ValueError:
            print("Відповідь прийшла не в форматі JSON")

        # NBU returns list of {cc: 'USD', rate: 40.1234, ...}
        m: Dict[str, float] = {"UAH": 1.0}

        if not isinstance(data, list):
            raise ValueError("Unexpected NBU response shape")

        for row in data:
            if not isinstance(row, dict):
                continue
            cc = (row.get("cc") or "").upper().strip()
            rate = row.get("rate")
            if not cc:
                continue
            if rate is None:
                continue
            try:
                m[cc] = float(rate)
            except Exception:
                continue

        # sanity: should have at least UAH + some majors
        if len(m) < 2:
            raise ValueError("NBU table is empty")

        return m

    async def _get_uah_per_1_map(self, as_of: date) -> Tuple[Dict[str, float], date]:
        """
        Gets cached day table; if missing, fetches.
        If requested date has no data (weekend/holiday), falls back to previous days (up to 7).
        Returns (rates_map, resolved_date) where rates_map includes UAH=1.0.
        """
        cached = self._day_cache_get(as_of)
        if cached is not None:
            return cached

        last_exc: Optional[Exception] = None

        # try requested day and go back up to 7 days
        for back in range(0, 8):
            d = as_of - timedelta(days=back)
            try:
                rates_map = await self._fetch_nbu_table_for_date(d)

                # ttl: short for today, long for historical
                ttl = 60 * 30 if d == date.today() else 60 * 60 * 24 * 90

                # cache under requested key but store resolved_date
                self._day_cache_set(as_of, rates_map, d, ttl)
                return rates_map, d
            except Exception as e:
                last_exc = e
                continue

        raise ValueError(f"FX day table not available for {as_of.isoformat()} (fallback failed)") from last_exc

    async def get_rate(self, base: str, quote: str, as_of: date) -> FxRate:
        base = base.upper().strip()
        quote = quote.upper().strip()

        if base == quote:
            return FxRate(base=base, quote=quote, rate=1.0, as_of=as_of)

        key = (as_of, base, quote)
        cached = self._cache_get(key)
        if cached is not None:
            return FxRate(base=base, quote=quote, rate=cached, as_of=as_of)

        rates_map, resolved_date = await self._get_uah_per_1_map(as_of)

        if base not in rates_map:
            raise ValueError(f"FX rate not available for base currency {base} on {resolved_date.isoformat()}")
        if quote not in rates_map:
            raise ValueError(f"FX rate not available for quote currency {quote} on {resolved_date.isoformat()}")

        # rates_map[X] = UAH per 1 X
        uah_per_1_base = rates_map[base]
        uah_per_1_quote = rates_map[quote]

        # base -> quote:
        # (1 base) = uah_per_1_base UAH
        # (uah_per_1_base UAH) in quote = uah_per_1_base / uah_per_1_quote
        rate = uah_per_1_base / uah_per_1_quote

        ttl = 60 * 30 if resolved_date == date.today() else 60 * 60 * 24 * 90
        self._cache_set(key, float(rate), ttl)

        return FxRate(base=base, quote=quote, rate=float(rate), as_of=resolved_date)

    async def get_rates(self, base: str, quotes: list[str], as_of: date) -> dict[str, float]:
        """
        Returns mapping: QUOTE -> rate (1 base = rate quote), for the same resolved as_of date.
        Uses NBU table + cross-rate via UAH.
        """
        base = base.upper().strip()
        quotes = [(q or "").upper().strip() for q in quotes]
        quotes = [q for q in quotes if q and q != base]

        if not quotes:
            return {}

        rates_map, resolved_date = await self._get_uah_per_1_map(as_of)

        if base not in rates_map:
            raise ValueError(f"FX rate not available for base currency {base} on {resolved_date.isoformat()}")

        uah_per_1_base = rates_map[base]

        out: dict[str, float] = {}
        for q in quotes:
            if q not in rates_map:
                continue
            uah_per_1_quote = rates_map[q]
            out[q] = float(uah_per_1_base / uah_per_1_quote)

        ttl = 60 * 30 if resolved_date == date.today() else 60 * 60 * 24 * 90
        for q, r in out.items():
            self._cache_set((resolved_date, base, q), float(r), ttl)

        return out


fx_service_singleton = FxService()
