from datetime import datetime, date
from zoneinfo import ZoneInfo
from app.core.config import settings


def tzinfo():
    return ZoneInfo(settings.default_timezone)


def month_range_kyiv(month: str) -> tuple[datetime, datetime]:
    # month: YYYY-MM
    try:
        y, m, d = month.split("-")
    except Exception:
        y, m = month.split("-")
    year = int(y)
    mon = int(m)
    start_local = datetime(year, mon, 1, 0, 0, 0, tzinfo=tzinfo())

    if mon == 12:
        end_local = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tzinfo())
    else:
        end_local = datetime(year, mon + 1, 1, 0, 0, 0, tzinfo=tzinfo())
    return start_local, end_local


def date_to_safe_noon(dt: date) -> datetime:
    # for CSV date-only import, choose 12:00 local to avoid DST gaps
    return datetime(dt.year, dt.month, dt.day, 12, 0, 0, tzinfo=tzinfo())
