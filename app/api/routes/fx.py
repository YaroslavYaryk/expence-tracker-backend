from datetime import date
from fastapi import APIRouter, Query
from app.services.fx_service import fx_service_singleton

router = APIRouter(prefix="/fx", tags=["fx"])


def parse_ymd(s: str) -> date:
    y, m, d = [int(x) for x in s.split("-")]
    return date(y, m, d)


@router.get("/rate")
async def get_rate(
        base: str = Query(..., min_length=3, max_length=8),
        quote: str = Query(..., min_length=3, max_length=8),
        asOf: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    fx = await fx_service_singleton.get_rate(base=base, quote=quote, as_of=parse_ymd(asOf))
    return {"base": fx.base, "quote": fx.quote, "asOf": fx.as_of.isoformat(), "rate": fx.rate}


@router.get("/latest")
async def latest(
        base: str = Query(..., min_length=3, max_length=8),
        quote: str = Query(..., min_length=3, max_length=8),
):
    fx = await fx_service_singleton.get_rate(base=base, quote=quote, as_of=date.today())
    return {"base": fx.base, "quote": fx.quote, "asOf": fx.as_of.isoformat(), "rate": fx.rate}


@router.get("/quotes")
async def fx_quotes(
        base: str = Query(..., min_length=3, max_length=8),
        symbols: str = Query(..., description="Comma-separated list, e.g. USD,EUR,CZK"),
        asOf: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    as_of_date = date.fromisoformat(asOf)
    quotes = [x.strip().upper() for x in symbols.split(",") if x.strip()]

    rates = await fx_service_singleton.get_rates(base=base, quotes=quotes, as_of=as_of_date)

    return {
        "base": base.upper(),
        "asOf": as_of_date.isoformat(),
        "rates": rates,  # { "USD": 0.0xx, "EUR": 0.0yy, ... }
    }
