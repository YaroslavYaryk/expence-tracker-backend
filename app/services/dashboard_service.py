from sqlalchemy.orm import Session
from sqlalchemy import select, func, case
from app.core.time import month_range_kyiv
from app.core.money import cents_to_amount_str
from app.models.transaction import Transaction
from app.repositories.categories_repo import CategoriesRepo


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.cat_repo = CategoriesRepo(db)

    def summary(self, user, month: str):
        from_ts, to_ts = month_range_kyiv(month)

        totals = self.db.execute(
            select(
                func.coalesce(func.sum(case((Transaction.type == 1, Transaction.amount_cents), else_=0)), 0).label("income"),
                func.coalesce(func.sum(case((Transaction.type == 0, Transaction.amount_cents), else_=0)), 0).label("expense"),
            ).where(
                Transaction.user_id == user.id,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
        ).one()

        income = int(totals.income)
        expense = int(totals.expense)
        balance = income - expense

        by_cat_rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount_cents), 0).label("total"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
            .group_by(Transaction.category_id)
        ).all()

        by_category = [{"categoryId": str(r[0]), "total": cents_to_amount_str(int(r[1]))} for r in by_cat_rows]

        recent_rows = self.db.execute(
            select(Transaction)
            .where(
                Transaction.user_id == user.id,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
            .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
            .limit(10)
        ).scalars().all()

        recent = []
        for tx in recent_rows:
            cat = self.cat_repo.get_user_category(user.id, tx.category_id)

            recent.append(
                {
                    "id": str(tx.id),
                    "type": "income" if tx.type == 1 else "expense",

                    # base amount (what analytics uses)
                    "amount": cents_to_amount_str(tx.amount_cents),
                    "currency": tx.currency,  # base currency

                    "occurredAt": tx.occurred_at.isoformat(),

                    "categoryId": str(tx.category_id),
                    "categoryName": cat.name if cat else "Unknown",
                    "categoryIcon": cat.icon if cat else None,

                    # NEW: original input + FX audit
                    "originalAmount": cents_to_amount_str(tx.original_amount_cents),
                    "originalCurrency": tx.original_currency,
                    "fxRateToBase": float(tx.fx_rate_to_base) if tx.fx_rate_to_base is not None else 1.0,
                    "fxDate": tx.fx_date.isoformat() if tx.fx_date is not None else tx.occurred_at.date().isoformat(),
                }
            )

        return {
            "month": month,

            # NEW: base currency for all totals in this response
            "baseCurrency": user.base_currency,

            "incomeTotal": cents_to_amount_str(income),
            "expenseTotal": cents_to_amount_str(expense),
            "balance": cents_to_amount_str(balance),
            "byCategory": by_category,
            "recent": recent,
        }
