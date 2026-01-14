from __future__ import annotations

from pydantic import BaseModel


class DashboardCategoryDto(BaseModel):
    categoryId: str
    total: str  # base total string ("1234.00")


class DashboardCategoryOriginalDto(BaseModel):
    categoryId: str
    currency: str
    total: str  # original total in that currency ("1234.00")
    name: str
    icon: str | None = None
    percent: float  # percent within this currency totals (0..100)


class DashboardRecentDto(BaseModel):
    id: str
    type: str

    # base (storage / analytics)
    amount: str
    currency: str

    occurredAt: str

    categoryId: str
    categoryName: str
    categoryIcon: str | None = None

    # original input + FX audit
    originalAmount: str
    originalCurrency: str
    fxRateToBase: float
    fxDate: str

    note: str | None = None


class DashboardSummaryResponse(BaseModel):
    month: str
    baseCurrency: str

    # base totals
    incomeTotal: str
    expenseTotal: str
    balance: str

    # totals by original currency (no conversion)
    incomeTotalByOriginal: dict[str, str]
    expenseTotalByOriginal: dict[str, str]

    # base by-category (kept for backward compatibility)
    byCategory: list[DashboardCategoryDto]

    # NEW: by-category totals in ORIGINAL currencies (no conversion)
    expenseByCategoryByOriginal: list[DashboardCategoryOriginalDto]

    recent: list[DashboardRecentDto]
