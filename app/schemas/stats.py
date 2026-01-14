from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Dict

class StatsByCategoryItem(BaseModel):
    categoryId: str
    name: str
    icon: str | None = None
    total: str    # base total (UAH) as string
    percent: float


class StatsByCategoryOriginalItem(BaseModel):
    categoryId: str
    currency: str
    name: str
    icon: str | None = None
    total: str    # original total in that currency as string
    percent: float


class StatsSummaryResponse(BaseModel):
    # Використовуємо validation_alias, щоб Pydantic знав,
    # що вхідне поле 'from' треба покласти в 'from_'
    from_: str = Field(validation_alias="from")
    to: str
    baseCurrency: str

    incomeTotal: str
    expenseTotal: str
    balance: str

    incomeTotalByOriginal: Dict[str, str]
    expenseTotalByOriginal: Dict[str, str]

    byCategory: List[StatsByCategoryItem]
    expenseByCategoryByOriginal: List[StatsByCategoryOriginalItem]

    model_config = {
        # Дозволяє використовувати як 'from', так і 'from_' при створенні об'єкта
        "populate_by_name": True
    }
