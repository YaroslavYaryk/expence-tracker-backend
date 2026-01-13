import re
from decimal import Decimal, InvalidOperation

_AMOUNT_RE = re.compile(r"^\d+(\.\d{1,2})?$")


def amount_str_to_cents(amount: str) -> int:
    if amount is None:
        raise ValueError("Amount is required")
    s = str(amount).strip()
    if not s:
        raise ValueError("Amount is required")
    if not _AMOUNT_RE.match(s):
        raise ValueError("Invalid amount format")
    try:
        dec = Decimal(s)
    except InvalidOperation:
        raise ValueError("Invalid amount")
    if dec <= 0:
        raise ValueError("Amount must be greater than 0")
    # exact to 2 decimals (no rounding beyond input)
    cents = int((dec * 100).to_integral_value())
    return cents


def cents_to_amount_str(cents: int) -> str:
    if cents is None:
        return "0.00"
    sign = "-" if cents < 0 else ""
    cents_abs = abs(int(cents))
    whole = cents_abs // 100
    frac = cents_abs % 100
    return f"{sign}{whole}.{frac:02d}"
