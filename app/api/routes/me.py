from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.schemas.user import MeResponse

router = APIRouter(tags=["me"])

@router.get("/me", response_model=MeResponse)
def me(user=Depends(get_current_user)):
    return {
        "id": str(user.id),
        "externalAuthId": user.external_auth_id,
        "email": user.email,
        "fullName": user.full_name,
        "timezone": user.timezone,
        "currency": user.currency,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
        'baseCurrency': user.base_currency,
        'displayCurrency': user.display_currency,
    }
