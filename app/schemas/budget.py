from pydantic import BaseModel, Field
from typing import Literal, Optional

BudgetStatus = Literal["on_track", "warning", "over"]


class BudgetItemDto(BaseModel):
    id: str
    categoryId: str
    categoryName: str
    categoryIcon: str | None = None
    limit: str
    spent: str
    remaining: str
    status: BudgetStatus
    currency: str = Field(default="UAH", min_length=3, max_length=8)  # input currency



class BudgetsResponse(BaseModel):
    month: str
    items: list[BudgetItemDto]


class BudgetCreate(BaseModel):
    month: str = Field(min_length=7, max_length=7)  # YYYY-MM
    categoryId: str
    limit: str
    currency: str = Field(default="CZK", min_length=3, max_length=8)  # input currency


class BudgetCreateResponse(BaseModel):
    id: str


class BudgetUpdate(BaseModel):
    limit: Optional[str] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=8)  # optional input currency change
