import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, DateTime, SmallInteger, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "type", "name", name="uq_categories_user_type_name"),
        Index("ix_categories_user_type_arch_pos", "user_id", "type", "is_archived", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # 0=expense, 1=income
    type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    icon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
