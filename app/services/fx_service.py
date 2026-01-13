from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Tuple, Optional

import httpx

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

    async def _fetch_nbu_table_for_date(self, d: date) -> Tuple[Dict[str, float], date]:
        """
        Returns (uah_per_1_map, resolved_date).
        NBU JSON rows contain:
          - cc: currency code (e.g. "USD")
          - rate: UAH per 1 unit of cc
          - exchangedate: "DD.MM.YYYY"
        """
        params = {"date": self._ymd_compact(d), "json": ""}

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(NBU_EXCHANGE_URL, params=params)
            r.raise_for_status()
            data = r.json()

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError("NBU returned empty rates list")

        # parse resolved_date from first row's exchangedate (dd.mm.yyyy)
        ex_date_raw = str(data[0].get("exchangedate") or "")
        resolved = d
        try:
            # "12.01.2026"
            day, month, year = ex_date_raw.split(".")
            resolved = date(int(year), int(month), int(day))
        except Exception:
            resolved = d

        rates: Dict[str, float] = {"UAH": 1.0}

        for row in data:
            cc = str(row.get("cc") or "").upper().strip()
            if not cc:
                continue
            try:
                rate = float(row.get("rate"))
            except Exception:
                continue
            # NBU "rate" is UAH per 1 unit of currency cc
            rates[cc] = rate

        return rates, resolved

    async def _get_uah_per_1_map(self, as_of: date) -> Tuple[Dict[str, float], date]:
        cached = self._day_cache_get(as_of)
        if cached is not None:
            return cached

        # If requested date has no data (weekend/holiday), fall back to previous days (up to 7)
        last_exc: Optional[Exception] = None
        for back in range(0, 8):
            d = as_of - timedelta(days=back)
            try:
                rates_map, resolved_date = await self._fetch_nbu_table_for_date(d)
                ttl = 60 * 30 if resolved_date == date.today() else 60 * 60 * 24 * 90
                self._day_cache_set(as_of, rates_map, resolved_date, ttl)
                return rates_map, resolved_date
            except Exception as e:
                last_exc = e
                continue

        raise ValueError(f"Unable to fetch NBU FX table for {as_of.isoformat()} (fallback failed): {last_exc}")

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


fx_service_singleton = FxService()
