from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.db import get_db
from app.core.security import get_current_user
from app.services.budgets_service import BudgetsService, month_to_first_day as month_to_date_first
from app.schemas.budget import BudgetsResponse, BudgetCreate, BudgetCreateResponse, BudgetUpdate

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=BudgetsResponse)
def list_budgets(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = BudgetsService(db)
    items = svc.list_with_progress(user, month)
    return {"month": month, "items": items}


@router.post("")
async def create_budget(
    payload: BudgetCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = BudgetsService(db)
    b_id = await svc.create(user=user, payload=payload)
    return {"id": str(b_id)}


@router.patch("/{budget_id}")
async def update_budget(
    budget_id: UUID,
    payload: BudgetUpdate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = BudgetsService(db)
    await svc.update(user=user, budget_id=budget_id, payload=payload)
    return {"ok": True}


@router.delete("/{budget_id}")
def delete_budget(budget_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = BudgetsService(db)
    svc.delete(user, UUID(budget_id))
    return {"ok": True}
