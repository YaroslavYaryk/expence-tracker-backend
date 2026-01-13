from pydantic import BaseModel


class DashboardCategoryDto(BaseModel):
    categoryId: str
    total: str


class DashboardRecentDto(BaseModel):
    id: str
    type: str

    # base amount
    amount: str
    currency: str

    occurredAt: str
    categoryId: str
    categoryName: str
    categoryIcon: str | None = None

    # NEW: original input + FX audit
    originalAmount: str
    originalCurrency: str
    fxRateToBase: float
    fxDate: str


class DashboardSummaryResponse(BaseModel):
    month: str

    # NEW: base currency for totals and base amounts in this response
    baseCurrency: str

    incomeTotal: str
    expenseTotal: str
    balance: str

    byCategory: list[DashboardCategoryDto]
    recent: list[DashboardRecentDto]
