from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.core.time import month_range_kyiv
from app.core.money import cents_to_amount_str
from app.services.transactions_service import TransactionsService, pm_to_str
from app.repositories.categories_repo import CategoriesRepo

from app.schemas.transaction import (
    TransactionsResponse, TransactionCreate, TransactionCreateResponse, TransactionUpdate,
    TransactionDto, TransactionCategoryDto
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionsResponse)
def list_transactions(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    type: str | None = Query(default=None, pattern="^(expense|income)$"),
    categoryId: str | None = None,
    paymentMethod: str | None = Query(default=None, pattern="^(cash|card|transfer|other)$"),
    q: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from_ts, to_ts = month_range_kyiv(month)
    lim = limit or settings.transactions_page_size_default
    lim = min(max(lim, 1), settings.transactions_page_size_max)

    svc = TransactionsService(db)
    category_uuid = UUID(categoryId) if categoryId else None
    items, next_cursor = svc.list(user, from_ts, to_ts, type, category_uuid, paymentMethod, q, lim, cursor)

    cat_repo = CategoriesRepo(db)
    dtos = []
    for tx in items:
        cat = cat_repo.get_user_category(user.id, tx.category_id)
        dtos.append(
            TransactionDto(
                id=str(tx.id),
                type="income" if tx.type == 1 else "expense",
                amount=cents_to_amount_str(tx.amount_cents),
                currency=tx.currency,
                occurredAt=tx.occurred_at.isoformat(),
                category=TransactionCategoryDto(
                    id=str(tx.category_id),
                    name=cat.name if cat else "Unknown",
                    icon=cat.icon if cat else None,
                ),
                paymentMethod=pm_to_str(tx.payment_method),
                note=tx.note,
                createdAt=tx.created_at.isoformat(),
                updatedAt=tx.updated_at.isoformat(),

                # NEW: FX/original
                originalAmount=cents_to_amount_str(tx.original_amount_cents),
                originalCurrency=tx.original_currency,
                fxRateToBase=float(tx.fx_rate_to_base) if tx.fx_rate_to_base is not None else 1.0,
                fxDate=tx.fx_date.isoformat() if tx.fx_date is not None else tx.occurred_at.date().isoformat(),
            )
        )

    return {"items": dtos, "nextCursor": next_cursor}

@router.post("")
async def create_transaction(
    payload: TransactionCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = TransactionsService(db)
    tx_id = await svc.create(user=user, payload=payload)
    return {"id": str(tx_id)}


@router.patch("/{tx_id}")
async def update_transaction(
    tx_id: UUID,
    payload: TransactionUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = TransactionsService(db)
    await svc.update(user=user, tx_id=tx_id, payload=payload)
    return {"ok": True}


@router.delete("/{tx_id}")
def delete_transaction(tx_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = TransactionsService(db)
    svc.delete(user, UUID(tx_id))
    return {"ok": True}


@router.get("/{tx_id}", response_model=TransactionDto)
def get_transaction(
    tx_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tx_uuid = UUID(tx_id)

    tx_service = TransactionsService(db)
    tx = tx_service.get_by_id(user, tx_uuid)

    if not tx:
        from app.core.errors import AppError
        raise AppError("NOT_FOUND", "Transaction not found", status_code=404)

    cat_repo = CategoriesRepo(db)
    cat = cat_repo.get_user_category(user.id, tx.category_id)

    return TransactionDto(
        id=str(tx.id),
        type="income" if tx.type == 1 else "expense",
        amount=cents_to_amount_str(tx.amount_cents),
        currency=tx.currency,
        occurredAt=tx.occurred_at.isoformat(),
        category=TransactionCategoryDto(
            id=str(tx.category_id),
            name=cat.name if cat else "Unknown",
            icon=cat.icon if cat else None,
        ),
        paymentMethod=pm_to_str(tx.payment_method),
        note=tx.note,
        createdAt=tx.created_at.isoformat(),
        updatedAt=tx.updated_at.isoformat(),

        # NEW: FX/original
        originalAmount=cents_to_amount_str(tx.original_amount_cents),
        originalCurrency=tx.original_currency,
        fxRateToBase=float(tx.fx_rate_to_base) if tx.fx_rate_to_base is not None else 1.0,
        fxDate=tx.fx_date.isoformat() if tx.fx_date is not None else tx.occurred_at.date().isoformat(),
    )
