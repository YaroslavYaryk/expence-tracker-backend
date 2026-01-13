import base64
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy.orm import Session
from app.core.errors import AppError
from app.core.fx import convert_original_to_base_cents, money_str_to_cents, dt_to_fx_date
from app.schemas.transaction import TransactionCreate
from app.services.fx_service import fx_service_singleton
from app.repositories.transactions_repo import TransactionsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.models.transaction import Transaction

PM_FROM_STR = {"cash": 0, "card": 1, "transfer": 2, "other": 3}
TYPE_FROM_STR = {"expense": 0, "income": 1}

def tx_type_to_int(t: str) -> int:
    return 0 if t == "expense" else 1


def pm_to_int(pm: str) -> int:
    return {"cash": 0, "card": 1, "transfer": 2, "other": 3}[pm]


def pm_to_str(v: int) -> str:
    return {0: "cash", 1: "card", 2: "transfer", 3: "other"}.get(v, "other")


def encode_cursor(occurred_at: datetime, tx_id) -> str:
    raw = f"{occurred_at.isoformat()}|{str(tx_id)}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

def _normalize_ccy(ccy: str) -> str:
    return (ccy or "").upper().strip()

def decode_cursor(cursor: str):
    if not cursor:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        dt_str, id_str = raw.split("|", 1)
        return datetime.fromisoformat(dt_str), UUID(id_str)
    except Exception:
        raise AppError("VALIDATION_ERROR", "Invalid cursor", status_code=400)


class TransactionsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TransactionsRepo(db)
        self.cat_repo = CategoriesRepo(db)

    def ensure_category(self, user_id, category_id):
        cat = self.cat_repo.get_user_category(user_id, category_id)
        if not cat or cat.is_archived:
            raise AppError("VALIDATION_ERROR", "Invalid category", status_code=400)
        return cat

    async def _compute_fx_fields(
        self,
        *,
        user,
        occurred_at: datetime,
        original_amount: str,
        original_currency: str,
    ) -> dict:
        base = _normalize_ccy(user.base_currency)
        original_currency = _normalize_ccy(original_currency)

        fx_date = dt_to_fx_date(occurred_at)

        if original_currency == base:
            rate = Decimal("1")
        else:
            fx = await fx_service_singleton.get_rate(
                base=original_currency,
                quote=base,
                as_of=fx_date,
            )
            rate = Decimal(str(fx.rate))

        amount_cents_base = convert_original_to_base_cents(original_amount, rate)
        original_amount_cents = money_str_to_cents(original_amount)

        return {
            "amount_cents": amount_cents_base,
            "currency": base,
            "original_amount_cents": original_amount_cents,
            "original_currency": original_currency,
            "fx_rate_to_base": rate,
            "fx_date": fx_date,
        }

    def _validate_category_matches_type(self, *, user_id: UUID, category_id: UUID, type_int: int) -> None:
        cat = self.cat_repo.get_user_category(user_id, category_id)
        if not cat:
            raise AppError("VALIDATION_ERROR", "Category not found", status_code=400)
        if cat.type != type_int:
            raise AppError("VALIDATION_ERROR", "Category type does not match transaction type", status_code=400)

    async def create(
        self,
        *,
        user,
        payload: TransactionCreate,
    ) -> UUID:
        # payload is TransactionCreateInput
        type_int = TYPE_FROM_STR[payload.type]

        category_id = UUID(payload.categoryId)
        self._validate_category_matches_type(user_id=user.id, category_id=category_id, type_int=type_int)

        occurred_at = payload.occurredAt

        fx_fields = await self._compute_fx_fields(
            user=user,
            occurred_at=occurred_at,
            original_amount=payload.amount,
            original_currency=payload.currency or user.base_currency,
        )

        tx = Transaction(
            user_id=user.id,
            type=type_int,
            amount_cents=fx_fields["amount_cents"],
            currency=fx_fields["currency"],
            occurred_at=occurred_at,
            category_id=category_id,
            payment_method=PM_FROM_STR.get(payload.paymentMethod, 3),
            note=(payload.note.strip() if payload.note else None),
            client_ref=payload.clientRef,
            source=0,  # keep whatever you use; 0 = manual
            original_amount_cents=fx_fields["original_amount_cents"],
            original_currency=fx_fields["original_currency"],
            fx_rate_to_base=fx_fields["fx_rate_to_base"],
            fx_date=fx_fields["fx_date"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.repo.create(tx)
        self.db.commit()
        return tx.id

    async def update(
        self,
        *,
        user,
        tx_id: UUID,
        payload,
    ) -> None:
        # payload is TransactionUpdateInput
        tx = self.tx_repo.get_by_id(user.id, tx_id)
        if not tx:
            raise AppError("NOT_FOUND", "Transaction not found", status_code=404)

        # Determine new type
        new_type_int = tx.type
        if payload.type is not None:
            new_type_int = TYPE_FROM_STR.get(payload.type)
            if new_type_int is None:
                raise AppError("VALIDATION_ERROR", "Invalid type", status_code=400)

        # Determine new occurred_at
        new_occurred_at = tx.occurred_at
        if payload.occurredAt is not None:
            new_occurred_at = payload.occurredAt

        # Determine new category_id (validate with new_type)
        new_category_id = tx.category_id
        if payload.categoryId is not None:
            new_category_id = UUID(payload.categoryId)

        self._validate_category_matches_type(user_id=user.id, category_id=new_category_id, type_int=new_type_int)

        # Determine if we need FX recompute
        need_fx = False
        new_original_currency = tx.original_currency
        new_original_amount_cents = tx.original_amount_cents
        new_fx_rate_to_base = tx.fx_rate_to_base
        new_fx_date = tx.fx_date
        new_amount_cents = tx.amount_cents
        new_currency = _normalize_ccy(user.base_currency)

        if payload.currency is not None:
            need_fx = True
            new_original_currency = _normalize_ccy(payload.currency)

        if payload.amount is not None:
            need_fx = True

        if payload.occurredAt is not None:
            # fx_date depends on date too
            need_fx = True

        if need_fx:
            original_amount_str = payload.amount if payload.amount is not None else str(Decimal(tx.original_amount_cents) / Decimal("100"))
            original_currency = new_original_currency

            fx_fields = await self._compute_fx_fields(
                user=user,
                occurred_at=new_occurred_at,
                original_amount=original_amount_str,
                original_currency=original_currency,
            )

            new_amount_cents = fx_fields["amount_cents"]
            new_currency = fx_fields["currency"]
            new_original_amount_cents = fx_fields["original_amount_cents"]
            new_original_currency = fx_fields["original_currency"]
            new_fx_rate_to_base = fx_fields["fx_rate_to_base"]
            new_fx_date = fx_fields["fx_date"]

        # Apply
        tx.type = new_type_int
        tx.occurred_at = new_occurred_at
        tx.category_id = new_category_id

        if payload.paymentMethod is not None:
            tx.payment_method = PM_FROM_STR.get(payload.paymentMethod, 3)

        if payload.note is not None:
            tx.note = payload.note.strip() if payload.note else None

        tx.amount_cents = new_amount_cents
        tx.currency = new_currency

        tx.original_amount_cents = int(new_original_amount_cents)
        tx.original_currency = new_original_currency
        tx.fx_rate_to_base = new_fx_rate_to_base
        tx.fx_date = new_fx_date

        tx.updated_at = datetime.utcnow()

        self.tx_repo.save(tx)
        self.db.commit()

    def delete(self, user, tx_id: UUID):
        count = self.repo.delete(user.id, tx_id)
        if count == 0:
            raise AppError("NOT_FOUND", "Transaction not found", status_code=404)
        self.db.commit()

    def list(self, user, from_ts, to_ts, type_str, category_id, payment_method, q_text, limit, cursor):
        type_int = tx_type_to_int(type_str) if type_str else None
        pm_int = pm_to_int(payment_method) if payment_method else None
        cursor_dt, cursor_id = decode_cursor(cursor) if cursor else (None, None)

        items = self.repo.list_cursor(
            user_id=user.id,
            from_ts=from_ts,
            to_ts=to_ts,
            type_int=type_int,
            category_id=category_id,
            payment_method_int=pm_int,
            q_text=(q_text or "").strip() if q_text else None,
            limit=limit,
            cursor_occurred_at=cursor_dt,
            cursor_id=cursor_id,
        )

        next_cursor = None
        if len(items) == limit:
            last = items[-1]
            next_cursor = encode_cursor(last.occurred_at, last.id)

        return items, next_cursor

    def get_by_id(self, user, tx_id: UUID) -> Transaction:
        tx = self.repo.get_by_id(user.id, tx_id)
        if not tx:
            raise AppError("NOT_FOUND", "Transaction not found", status_code=404)

        return tx


