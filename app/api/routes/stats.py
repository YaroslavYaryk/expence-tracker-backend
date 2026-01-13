from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func, case, text

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.errors import AppError
from app.core.money import cents_to_amount_str
from app.models.transaction import Transaction
from app.models.category import Category

router = APIRouter(prefix="/stats", tags=["stats"])

def parse_ymd(s: str) -> date:
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        raise AppError("VALIDATION_ERROR", "Invalid date format. Use YYYY-MM-DD", status_code=400)

def make_bounds(from_date: str, to_date: str):
    d_from = parse_ymd(from_date)
    d_to = parse_ymd(to_date)
    if d_to < d_from:
        raise AppError("VALIDATION_ERROR", "`to` must be >= `from`", status_code=400)

    from_ts = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0).astimezone()
    to_ts_exclusive = datetime(d_to.year, d_to.month, d_to.day, 0, 0, 0).astimezone() + timedelta(days=1)
    return d_from, d_to, from_ts, to_ts_exclusive

@router.get("/summary")
def summary(
    from_date: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d_from, d_to, from_ts, to_ts_exclusive = make_bounds(from_date, to_date)

    # Totals (income/expense)
    totals_stmt = (
        select(
            func.coalesce(func.sum(case((Transaction.type == 1, Transaction.amount_cents), else_=0)), 0).label("income"),
            func.coalesce(func.sum(case((Transaction.type == 0, Transaction.amount_cents), else_=0)), 0).label("expense"),
        )
        .where(
            Transaction.user_id == user.id,
            Transaction.occurred_at >= from_ts,
            Transaction.occurred_at < to_ts_exclusive,
        )
    )

    income_cents, expense_cents = db.execute(totals_stmt).one()
    income_cents = int(income_cents or 0)
    expense_cents = int(expense_cents or 0)
    balance_cents = income_cents - expense_cents

    # Expenses by category (join categories for name/icon)
    by_cat_stmt = (
        select(
            Transaction.category_id.label("category_id"),
            func.coalesce(func.sum(Transaction.amount_cents), 0).label("total_cents"),
            Category.name.label("category_name"),
            Category.icon.label("category_icon"),
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(
            Transaction.user_id == user.id,
            Transaction.type == 0,  # expense
            Transaction.occurred_at >= from_ts,
            Transaction.occurred_at < to_ts_exclusive,
        )
        .group_by(Transaction.category_id, Category.name, Category.icon)
        .order_by(func.coalesce(func.sum(Transaction.amount_cents), 0).desc())
    )

    rows = db.execute(by_cat_stmt).all()

    by_category = []
    for category_id, total_cents, name, icon in rows:
        total_cents = int(total_cents or 0)
        pct = (total_cents / expense_cents * 100.0) if expense_cents > 0 else 0.0
        by_category.append(
            {
                "categoryId": str(category_id),
                "name": name,
                "icon": icon,
                "total": cents_to_amount_str(total_cents),
                "percent": round(pct, 2),
            }
        )

    return {
        "from": d_from.isoformat(),
        "to": d_to.isoformat(),
        "incomeTotal": cents_to_amount_str(income_cents),
        "expenseTotal": cents_to_amount_str(expense_cents),
        "balance": cents_to_amount_str(balance_cents),
        "byCategory": by_category,
    }

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
