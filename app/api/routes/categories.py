from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.core.security import get_current_user
from app.services.categories_service import CategoriesService
from app.schemas.category import (
    CategoriesResponse, CategoryCreate, CategoryCreateResponse, CategoryUpdate, CategoryDto
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoriesResponse)
def list_categories(
    type: str = Query(..., pattern="^(expense|income)$"),
    includeArchived: bool = False,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = CategoriesService(db)
    cats = svc.list(user.id, type, includeArchived)
    items = []
    for c in cats:
        items.append(
            CategoryDto(
                id=str(c.id),
                type="expense" if c.type == 0 else "income",
                name=c.name,
                icon=c.icon,
                color=c.color,
                isDefault=c.is_default,
                isArchived=c.is_archived,
                position=c.position,
            )
        )
    return {"items": items}


@router.post("", response_model=CategoryCreateResponse, status_code=201)
def create_category(payload: CategoryCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CategoriesService(db)
    cat = svc.create(user.id, payload.type, payload.name, payload.icon, payload.color, payload.position)
    return {"id": str(cat.id)}


@router.patch("/{category_id}")
def update_category(category_id: str, payload: CategoryUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    svc = CategoriesService(db)
    fields = payload.model_dump(exclude_unset=True)
    svc.update(user.id, category_id, fields)
    return {"ok": True}
