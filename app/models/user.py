import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_auth_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Europe/Kyiv")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CZK")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    base_currency = mapped_column(String(3), nullable=False, default="UAH")
    display_currency = mapped_column(String(3), nullable=False, default="CZK")
