from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select, func, case

from app.core.money import cents_to_amount_str
from app.models.transaction import Transaction
from app.repositories.categories_repo import CategoriesRepo


def _day_range_kyiv(d: date):
    # якщо у тебе вже є утиліта — використай її; тут простий варіант (naive)
    start = datetime.combine(d, time.min)
    end = datetime.combine(d, time.min).replace(day=d.day)  # placeholder
    # правильніше:
    end = datetime.combine(d, time.min)
    end = end.replace()  # no-op, залишаю для сумісності
    # ми нижче не використовуємо _day_range_kyiv, тому можна видалити зовсім
    return start, end


class StatsService:
    def __init__(self, db: Session):
        self.db = db
        self.cat_repo = CategoriesRepo(db)

    def summary(self, user, from_date: date, to_date: date):
        # inclusive day range -> [from_ts, to_ts_exclusive)
        from_ts = datetime.combine(from_date, time.min)
        to_ts_exclusive = datetime.combine(to_date, time.min) + timedelta(days=1)

        # -------------------------
        # 1) base totals
        # -------------------------
        totals = self.db.execute(
            select(
                func.coalesce(
                    func.sum(case((Transaction.type == 1, Transaction.amount_cents), else_=0)), 0
                ).label("income"),
                func.coalesce(
                    func.sum(case((Transaction.type == 0, Transaction.amount_cents), else_=0)), 0
                ).label("expense"),
            ).where(
                Transaction.user_id == user.id,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts_exclusive,
            )
        ).one()

        income = int(totals.income)
        expense = int(totals.expense)
        balance = income - expense

        # -------------------------
        # 2) totals by original currency (no conversion)
        # -------------------------
        orig_rows = self.db.execute(
            select(
                Transaction.original_currency,
                func.coalesce(
                    func.sum(case((Transaction.type == 1, Transaction.original_amount_cents), else_=0)), 0
                ).label("income"),
                func.coalesce(
                    func.sum(case((Transaction.type == 0, Transaction.original_amount_cents), else_=0)), 0
                ).label("expense"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts_exclusive,
            )
            .group_by(Transaction.original_currency)
        ).all()

        income_by_orig: dict[str, str] = {}
        expense_by_orig: dict[str, str] = {}
        for cur, inc_cents, exp_cents in orig_rows:
            code = (cur or "").upper().strip()
            if not code:
                continue
            income_by_orig[code] = cents_to_amount_str(int(inc_cents))
            expense_by_orig[code] = cents_to_amount_str(int(exp_cents))

        # -------------------------
        # 3) base byCategory (expenses)
        # -------------------------
        by_cat_rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount_cents), 0).label("total"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts_exclusive,
            )
            .group_by(Transaction.category_id)
        ).all()

        total_expense_base = sum(int(r[1]) for r in by_cat_rows) if by_cat_rows else 0

        by_category = []
        for cat_id, total_cents in by_cat_rows:
            cat = self.cat_repo.get_user_category(user.id, cat_id)
            total_cents_int = int(total_cents)
            percent = (total_cents_int / total_expense_base * 100.0) if total_expense_base > 0 else 0.0
            by_category.append(
                {
                    "categoryId": str(cat_id),
                    "name": cat.name if cat else "Unknown",
                    "icon": cat.icon if cat else None,
                    "total": cents_to_amount_str(total_cents_int),
                    "percent": float(percent),
                }
            )
        by_category.sort(key=lambda x: -float(x["total"].replace(",", ".")))

        # -------------------------
        # 4) NEW: expenseByCategoryByOriginal (no conversion)
        # -------------------------
        by_cat_orig_rows = self.db.execute(
            select(
                Transaction.category_id,
                Transaction.original_currency,
                func.coalesce(func.sum(Transaction.original_amount_cents), 0).label("total"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts_exclusive,
            )
            .group_by(Transaction.category_id, Transaction.original_currency)
        ).all()

        totals_per_currency: dict[str, int] = {}
        for cat_id, cur, total_cents in by_cat_orig_rows:
            code = (cur or "").upper().strip()
            if not code:
                continue
            totals_per_currency[code] = totals_per_currency.get(code, 0) + int(total_cents)

        expense_by_category_by_original = []
        for cat_id, cur, total_cents in by_cat_orig_rows:
            code = (cur or "").upper().strip()
            if not code:
                continue

            cat = self.cat_repo.get_user_category(user.id, cat_id)
            total_cents_int = int(total_cents)
            denom = totals_per_currency.get(code, 0)
            percent = (total_cents_int / denom * 100.0) if denom > 0 else 0.0

            expense_by_category_by_original.append(
                {
                    "categoryId": str(cat_id),
                    "currency": code,
                    "name": cat.name if cat else "Unknown",
                    "icon": cat.icon if cat else None,
                    "total": cents_to_amount_str(total_cents_int),
                    "percent": float(percent),
                }
            )

        expense_by_category_by_original.sort(
            key=lambda x: (x["currency"], -float(x["total"].replace(",", ".")))
        )

        return {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "baseCurrency": (user.base_currency or "UAH").upper(),

            "incomeTotal": cents_to_amount_str(income),
            "expenseTotal": cents_to_amount_str(expense),
            "balance": cents_to_amount_str(balance),

            "incomeTotalByOriginal": income_by_orig,
            "expenseTotalByOriginal": expense_by_orig,

            "byCategory": by_category,

            # NEW
            "expenseByCategoryByOriginal": expense_by_category_by_original,
        }
