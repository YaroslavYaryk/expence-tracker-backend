from __future__ import annotations

import uuid
from datetime import datetime, date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, String, BigInteger, Date, Numeric
from app.core.db import Base

class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    category_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)

    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # "YYYY-MM"

    # base storage
    limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="UAH")

    # original input (what user entered)
    original_limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UAH")

    # FX audit
    fx_rate_to_base: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False, default=1.0)
    fx_date: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
