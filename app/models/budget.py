import uuid
from datetime import datetime, date
from sqlalchemy import Date, DateTime, BigInteger, String, ForeignKey, UniqueConstraint, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "month", "category_id", name="uq_budget_user_month_category"),
        Index("ix_budget_user_month_desc", "user_id", "month"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    month: Mapped[date] = mapped_column(Date, nullable=False)  # first day of month
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)

    limit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UAH")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    original_limit_cents = mapped_column(BigInteger, nullable=False)
    original_currency = mapped_column(String(3), nullable=False)

    fx_rate_to_base = mapped_column(Numeric(18, 8), nullable=False, default=1)
    fx_date = mapped_column(Date, nullable=False)
