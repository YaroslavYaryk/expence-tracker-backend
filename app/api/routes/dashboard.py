from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.services.dashboard_service import DashboardService
from app.schemas.dashboard import DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def summary(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = DashboardService(db)
    return svc.summary(user, month)
