from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.errors import AppError
from app.core.money import cents_to_amount_str
from app.core.fx import convert_original_to_base_cents, money_str_to_cents
from app.services.fx_service import fx_service_singleton
from app.core.time import month_range_kyiv
from app.repositories.budgets_repo import BudgetsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.models.budget import Budget
from app.models.transaction import Transaction


def _normalize_ccy(ccy: str) -> str:
    return (ccy or "").upper().strip()


def month_to_first_day(month: str) -> date:
    # month: YYYY-MM
    y, m = [int(x) for x in month.split("-")]
    return date(y, m, 1)


class BudgetsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BudgetsRepo(db)
        self.cat_repo = CategoriesRepo(db)

    async def _compute_fx_fields_for_budget(
        self,
        *,
        user,
        fx_date: date,
        original_limit: str,
        original_currency: str,
    ) -> dict:
        base = _normalize_ccy(user.base_currency)
        original_currency = _normalize_ccy(original_currency)

        if original_currency == base:
            rate = Decimal("1")
        else:
            fx = await fx_service_singleton.get_rate(base=original_currency, quote=base, as_of=fx_date)
            rate = Decimal(str(fx.rate))

        limit_cents_base = convert_original_to_base_cents(original_limit, rate)
        original_limit_cents = money_str_to_cents(original_limit)

        return {
            "limit_cents": limit_cents_base,
            "currency": base,
            "original_limit_cents": original_limit_cents,
            "original_currency": original_currency,
            "fx_rate_to_base": rate,
            "fx_date": fx_date,
        }

    def _validate_category_is_expense(self, *, user_id: UUID, category_id: UUID) -> None:
        cat = self.cat_repo.get_user_category(user_id, category_id)
        if not cat:
            raise AppError("VALIDATION_ERROR", "Category not found", status_code=400)
        if cat.type != 0:
            raise AppError("VALIDATION_ERROR", "Budgets are supported only for expense categories", status_code=400)

    async def create(self, *, user, payload) -> UUID:
        # payload is BudgetCreateInput
        fx_date = month_to_first_day(payload.month)

        category_id = UUID(payload.categoryId)
        self._validate_category_is_expense(user_id=user.id, category_id=category_id)

        fx_fields = await self._compute_fx_fields_for_budget(
            user=user,
            fx_date=fx_date,
            original_limit=payload.limit,
            original_currency=payload.currency or user.base_currency,
        )

        budget = Budget(
            user_id=user.id,
            month=datetime.strptime(payload.month, "%Y-%m").date(),
            category_id=category_id,
            limit_cents=fx_fields["limit_cents"],
            currency=fx_fields["currency"],
            original_limit_cents=fx_fields["original_limit_cents"],
            original_currency=fx_fields["original_currency"],
            fx_rate_to_base=fx_fields["fx_rate_to_base"],
            fx_date=fx_fields["fx_date"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.repo.create(budget)
        self.db.commit()
        return budget.id

    async def update(self, *, user, budget_id: UUID, payload) -> None:
        # payload is BudgetUpdateInput
        b = self.repo.get_by_id(user.id, budget_id)
        if not b:
            raise AppError("NOT_FOUND", "Budget not found", status_code=404)

        # fx_date stays stable for the budget month
        fx_date = b.fx_date if b.fx_date else month_to_first_day(b.month)

        need_fx = False
        new_original_currency = b.original_currency
        if payload.currency is not None:
            need_fx = True
            new_original_currency = _normalize_ccy(payload.currency)

        if payload.limit is not None:
            need_fx = True

        if need_fx:
            original_limit_str = payload.limit if payload.limit is not None else str(Decimal(b.original_limit_cents) / Decimal("100"))
            fx_fields = await self._compute_fx_fields_for_budget(
                user=user,
                fx_date=fx_date,
                original_limit=original_limit_str,
                original_currency=new_original_currency,
            )

            b.limit_cents = fx_fields["limit_cents"]
            b.currency = fx_fields["currency"]
            b.original_limit_cents = fx_fields["original_limit_cents"]
            b.original_currency = fx_fields["original_currency"]
            b.fx_rate_to_base = fx_fields["fx_rate_to_base"]
            b.fx_date = fx_fields["fx_date"]

        b.updated_at = datetime.utcnow()
        self.repo.save(b)
        self.db.commit()

    def delete(self, user, budget_id: UUID):
        count = self.repo.delete(user.id, budget_id)
        if count == 0:
            raise AppError("NOT_FOUND", "Budget not found", status_code=404)
        self.db.commit()

    def list_with_progress(self, user, month: str):
        month_date = month_to_first_day(month)
        budgets = self.repo.list_for_month(user.id, month_date)
        from_ts, to_ts = month_range_kyiv(month)

        # aggregate spent per category in one query
        spent_rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount_cents), 0).label("spent"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
            .group_by(Transaction.category_id)
        ).all()
        spent_map = {row[0]: int(row[1]) for row in spent_rows}

        # load categories (simple per-budget, small N)
        items = []
        for b in budgets:
            cat = self.cat_repo.get_user_category(user.id, b.category_id)
            spent = spent_map.get(b.category_id, 0)
            remaining = b.limit_cents - spent

            ratio = (spent / b.limit_cents) if b.limit_cents > 0 else 0
            if spent > b.limit_cents:
                status = "over"
            elif ratio >= 0.8:
                status = "warning"
            else:
                status = "on_track"

            items.append(
                {
                    "id": str(b.id),
                    "categoryId": str(b.category_id),
                    "categoryName": cat.name if cat else "Unknown",
                    "categoryIcon": cat.icon if cat else None,
                    "limit": cents_to_amount_str(b.limit_cents),
                    "spent": cents_to_amount_str(spent),
                    "remaining": cents_to_amount_str(remaining),
                    "status": status,
                }
            )
        return items
