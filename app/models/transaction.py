import uuid
from datetime import datetime
from sqlalchemy import (
    String, DateTime, SmallInteger, BigInteger, ForeignKey, Index, UniqueConstraint, Text, Date, Numeric
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_user_occurred_id_desc", "user_id", "occurred_at", "id"),
        Index("ix_tx_user_type_occurred_desc", "user_id", "type", "occurred_at"),
        Index("ix_tx_user_category_occurred_desc", "user_id", "category_id", "occurred_at"),
        UniqueConstraint("user_id", "client_ref", name="uq_tx_user_client_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 0=expense, 1=income
    type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UAH")

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)

    # 0=cash,1=card,2=transfer,3=other
    payment_method: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 0=manual,1=import_csv
    source: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    client_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    original_amount_cents = mapped_column(BigInteger, nullable=False)
    original_currency = mapped_column(String(3), nullable=False)

    fx_rate_to_base = mapped_column(Numeric(18, 8), nullable=False, default=1)
    fx_date = mapped_column(Date, nullable=False)
