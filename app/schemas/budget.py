from pydantic import BaseModel, Field
from typing import Literal, Optional

BudgetStatus = Literal["on_track", "warning", "over"]


class BudgetDto(BaseModel):
    id: str
    month: str

    categoryId: str
    categoryName: str
    categoryIcon: str | None = None

    # base amounts (analytics)
    limit: str
    spent: str
    remaining: str
    status: str
    baseCurrency: str

    # original input
    originalLimit: str
    originalCurrency: str
    fxRateToBase: float
    fxDate: str

    # NEW: expenses breakdown for this category in ORIGINAL currencies (no conversion)
    spentByOriginal: dict[str, str]

class BudgetCreateResponse(BaseModel):
    id: str

class BudgetsResponse(BaseModel):
    items: list[BudgetDto]


class BudgetCreate(BaseModel):
    month: str
    categoryId: str
    limit: str
    currency: str  # original currency


class BudgetUpdate(BaseModel):
    limit: str
    currency: str  # original currency