from datetime import datetime

from pydantic import BaseModel, Field
from typing import Literal, Optional
from uuid import UUID

from app.schemas.category import CategoryDto

TransactionType = Literal["expense", "income"]
PaymentMethod = Literal["cash", "card", "transfer", "other"]


class TransactionCategoryDto(BaseModel):
    id: str
    name: str
    icon: str | None = None


class TransactionDto(BaseModel):
    id: str
    type: Literal["expense", "income"]
    amount: str           # base amount string
    currency: str         # base currency
    occurredAt: str
    createdAt: str
    updatedAt: str
    paymentMethod: str
    note: Optional[str]
    category: TransactionCategoryDto

    originalAmount: str
    originalCurrency: str
    fxRateToBase: float
    fxDate: str


class TransactionsResponse(BaseModel):
    items: list[TransactionDto]
    nextCursor: str | None = None


class TransactionCreate(BaseModel):
    type: TransactionType
    amount: str
    currency: str = Field(default="CZK", min_length=3, max_length=3)  # input currency
    occurredAt: datetime
    categoryId: str
    paymentMethod: PaymentMethod
    note: str | None = Field(default=None, max_length=500)
    clientRef: str | None = Field(default=None, max_length=64)


class TransactionCreateResponse(BaseModel):
    id: str


class TransactionUpdate(BaseModel):
    amount: str | None = None
    occurredAt: str | None = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)  # optional change input currency
    categoryId: str | None = None
    paymentMethod: PaymentMethod | None = None
    note: str | None = Field(default=None, max_length=500)
