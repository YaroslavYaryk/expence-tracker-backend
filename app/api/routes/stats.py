from datetime import date, datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case
from sqlalchemy.orm import Session

from app.api.routes.fx import parse_ymd
from app.core.db import get_db
from app.core.errors import AppError
from app.core.money import cents_to_amount_str
from app.core.security import get_current_user
from app.models.transaction import Transaction
from app.schemas.stats import StatsSummaryResponse
from app.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/summary", response_model=StatsSummaryResponse)
def stats_summary(
    from_: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from_date = date.fromisoformat(from_)
    to_date = date.fromisoformat(to)

    svc = StatsService(db)
    return svc.summary(user, from_date, to_date)

@router.get("/timeseries")
def timeseries(
    from_date: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    granularity: str = Query("day", pattern=r"^(day|week|month)$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d_from = parse_ymd(from_date)
    d_to = parse_ymd(to_date)

    if d_to < d_from:
        raise AppError("VALIDATION_ERROR", "`to` must be >= `from`", status_code=400)

    # Inclusive date range [from..to] -> convert to timestamptz bounds
    # We'll treat "from" as start of day and "to" as end of day by using < (to + 1 day)
    from_ts = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0).astimezone()
    to_ts_exclusive = datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0).astimezone()
    # add 1 day
    to_ts_exclusive = to_ts_exclusive.replace()  # no-op, keep explicit
    to_ts_exclusive = to_ts_exclusive + (datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0) - datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0))  # no-op for type check

    # safer add day:
    from datetime import timedelta
    to_ts_exclusive = datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0).astimezone() + timedelta(days=1)

    # Postgres date_trunc buckets (week starts Monday)
    bucket_expr = func.date_trunc(granularity, Transaction.occurred_at).label("bucket")

    row = (
        select(
            bucket_expr,
            func.coalesce(func.sum(case((Transaction.type == 1, Transaction.amount_cents), else_=0)), 0).label("income"),
            func.coalesce(func.sum(case((Transaction.type == 0, Transaction.amount_cents), else_=0)), 0).label("expense"),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.occurred_at >= from_ts,
            Transaction.occurred_at < to_ts_exclusive,
        )
        .group_by(bucket_expr)
        .order_by(bucket_expr.asc())
    )

    rows = db.execute(row).all()

    points = []
    for bucket, income_cents, expense_cents in rows:
        income = int(income_cents)
        expense = int(expense_cents)
        balance = income - expense
        # return period as YYYY-MM-DD (day), week/month also as bucket date
        period = bucket.date().isoformat()
        points.append(
            {
                "period": period,
                "income": cents_to_amount_str(income),
                "expense": cents_to_amount_str(expense),
                "balance": cents_to_amount_str(balance),
            }
        )

    return {
        "granularity": granularity,
        "from": d_from.isoformat(),
        "to": d_to.isoformat(),
        "points": points,
    }