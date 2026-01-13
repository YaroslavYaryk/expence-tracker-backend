from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date


def money_str_to_decimal(s: str) -> Decimal:
    return Decimal(s.strip().replace(",", "."))


def decimal_to_cents(d: Decimal) -> int:
    cents = (d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))


def money_str_to_cents(s: str) -> int:
    return decimal_to_cents(money_str_to_decimal(s))


def convert_original_to_base_cents(original_amount_str: str, rate_to_base: Decimal) -> int:
    original = money_str_to_decimal(original_amount_str)
    base_amount = (original * rate_to_base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return decimal_to_cents(base_amount)


def dt_to_fx_date(dt: datetime) -> date:
    return dt.date()
