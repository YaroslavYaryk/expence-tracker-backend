from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.errors import AppError
from app.core.money import cents_to_amount_str, amount_str_to_cents
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


def _budget_status(limit_cents: int, spent_cents: int) -> str:
    if limit_cents <= 0:
        return "on_track"
    if spent_cents > limit_cents:
        return "over"
    if spent_cents >= int(limit_cents * 0.85):
        return "warning"
    return "on_track"

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

    async def create(self, user, month: str, category_id: UUID, limit_str: str, currency: str):
        base_cur = (user.base_currency or "UAH").upper()
        orig_cur = (currency or base_cur).upper().strip()

        orig_cents = amount_str_to_cents(limit_str)

        # FX date = first day of month (consistent)
        fx_date = date.fromisoformat(f"{month}-01")
        fx = await fx_service_singleton.get_rate(base=orig_cur, quote=base_cur, as_of=fx_date)

        limit_cents_base = int(round(orig_cents * fx.rate))

        b = Budget(
            user_id=user.id,
            category_id=category_id,
            month=month,

            base_currency=base_cur,
            limit_cents=limit_cents_base,

            original_limit_cents=orig_cents,
            original_currency=orig_cur,
            fx_rate_to_base=fx.rate,
            fx_date=fx.as_of,
        )
        self.db.add(b)
        self.db.commit()
        self.db.refresh(b)
        return b

    async def update(self, user, budget_id: UUID, limit_str: str, currency: str):
        b = self.db.execute(
            select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id)
        ).scalar_one_or_none()

        if not b:
            raise ValueError("Budget not found")

        base_cur = (b.base_currency or user.base_currency or "UAH").upper()
        orig_cur = (currency or base_cur).upper().strip()

        orig_cents = amount_str_to_cents(limit_str)
        fx_date = date.fromisoformat(f"{b.month}-01")
        fx = await fx_service_singleton.get_rate(base=orig_cur, quote=base_cur, as_of=fx_date)

        b.original_limit_cents = orig_cents
        b.original_currency = orig_cur
        b.fx_rate_to_base = fx.rate
        b.fx_date = fx.as_of

        b.limit_cents = int(round(orig_cents * fx.rate))

        self.db.commit()
        self.db.refresh(b)
        return b

    def delete(self, user, budget_id: UUID):
        count = self.repo.delete(user.id, budget_id)
        if count == 0:
            raise AppError("NOT_FOUND", "Budget not found", status_code=404)
        self.db.commit()

    def list(self, user, month: str):
        from_ts, to_ts = month_range_kyiv(month)

        budgets = self.db.execute(
            select(Budget).where(
                Budget.user_id == user.id,
                Budget.month == month,
            )
        ).scalars().all()

        if not budgets:
            return {"items": []}

        category_ids = [b.category_id for b in budgets]

        # 1) base spent by category (UAH)
        spent_base_rows = self.db.execute(
            select(
                Transaction.category_id,
                func.coalesce(func.sum(Transaction.amount_cents), 0).label("spent"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,  # expense
                Transaction.category_id.in_(category_ids),
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
            .group_by(Transaction.category_id)
        ).all()

        spent_base_map: dict[UUID, int] = {r[0]: int(r[1]) for r in spent_base_rows}

        # 2) NEW: original spent by category + currency
        spent_orig_rows = self.db.execute
        spent_orig_rows = self.db.execute(
            select(
                Transaction.category_id,
                Transaction.original_currency,
                func.coalesce(func.sum(Transaction.original_amount_cents), 0).label("spent"),
            )
            .where(
                Transaction.user_id == user.id,
                Transaction.type == 0,
                Transaction.category_id.in_(category_ids),
                Transaction.occurred_at >= from_ts,
                Transaction.occurred_at < to_ts,
            )
            .group_by(Transaction.category_id, Transaction.original_currency)
        ).all()

        # map: category_id -> { CUR: cents }
        spent_orig_map: dict[UUID, dict[str, int]] = {}
        for cat_id, cur, cents in spent_orig_rows:
            code = (cur or "").upper().strip()
            if not code:
                continue
            spent_orig_map.setdefault(cat_id, {})
            spent_orig_map[cat_id][code] = int(cents)

        # build DTOs
        items = []
        for b in budgets:
            cat = self.cat_repo.get_user_category(user.id, b.category_id)

            spent_cents = spent_base_map.get(b.category_id, 0)
            remaining_cents = int(b.limit_cents) - spent_cents

            status = _budget_status(int(b.limit_cents), spent_cents)

            # spentByOriginal for this category
            spent_by_orig_str: dict[str, str] = {}
            for cur, cents in (spent_orig_map.get(b.category_id, {}) or {}).items():
                spent_by_orig_str[cur] = cents_to_amount_str(int(cents))

            items.append(
                {
                    "id": str(b.id),
                    "month": b.month,
                    "categoryId": str(b.category_id),
                    "categoryName": cat.name if cat else "Unknown",
                    "categoryIcon": cat.icon if cat else None,

                    # base
                    "limit": cents_to_amount_str(int(b.limit_cents)),
                    "spent": cents_to_amount_str(spent_cents),
                    "remaining": cents_to_amount_str(remaining_cents),
                    "status": status,
                    "baseCurrency": (b.base_currency or user.base_currency or "UAH").upper(),

                    # original
                    "originalLimit": cents_to_amount_str(int(b.original_limit_cents)),
                    "originalCurrency": (b.original_currency or "UAH").upper(),
                    "fxRateToBase": float(b.fx_rate_to_base) if b.fx_rate_to_base is not None else 1.0,
                    "fxDate": b.fx_date.isoformat(),

                    # NEW
                    "spentByOriginal": spent_by_orig_str,
                }
            )

        return {"items": items}