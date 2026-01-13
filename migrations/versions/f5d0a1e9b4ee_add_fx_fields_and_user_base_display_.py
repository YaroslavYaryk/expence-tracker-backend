"""add fx fields and user base/display currency

Revision ID: f5d0a1e9b4ee
Revises: 0001_init
Create Date: 2026-01-12 20:16:46.639165

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5d0a1e9b4ee'
down_revision: Union[str, None] = '0001_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- users ---
    op.add_column("users", sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="UAH"))
    op.add_column("users", sa.Column("display_currency", sa.String(length=3), nullable=False, server_default="UAH"))

    # прибираємо server_default після backfill (не обов’язково, але краще)
    op.alter_column("users", "base_currency", server_default=None)
    op.alter_column("users", "display_currency", server_default=None)

    # --- transactions ---
    op.add_column("transactions", sa.Column("original_amount_cents", sa.BigInteger(), nullable=True))
    op.add_column("transactions", sa.Column("original_currency", sa.String(length=3), nullable=True))
    op.add_column("transactions", sa.Column("fx_rate_to_base", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("transactions", sa.Column("fx_date", sa.Date(), nullable=True))

    # Backfill existing transactions:
    # - original_amount_cents = amount_cents
    # - original_currency = currency
    # - fx_date = DATE(occurred_at)
    op.execute(
        """
        UPDATE transactions
        SET
          original_amount_cents = amount_cents,
          original_currency = currency,
          fx_date = CAST(occurred_at AS DATE)
        WHERE original_amount_cents IS NULL
           OR original_currency IS NULL
           OR fx_date IS NULL
        """
    )

    op.alter_column("transactions", "original_amount_cents", nullable=False)
    op.alter_column("transactions", "original_currency", nullable=False)
    op.alter_column("transactions", "fx_date", nullable=False)

    op.alter_column("transactions", "fx_rate_to_base", server_default=None)

    # --- budgets ---
    op.add_column("budgets", sa.Column("original_limit_cents", sa.BigInteger(), nullable=True))
    op.add_column("budgets", sa.Column("original_currency", sa.String(length=3), nullable=True))
    op.add_column("budgets", sa.Column("fx_rate_to_base", sa.Numeric(18, 8), nullable=False, server_default="1"))
    op.add_column("budgets", sa.Column("fx_date", sa.Date(), nullable=True))

    # Backfill budgets:
    # Якщо в тебе в таблиці budgets є limit_cents, використовуй його.
    # Якщо поле називається інакше — заміни тут.
    op.execute(
        """
        UPDATE budgets
        SET
          original_limit_cents = limit_cents,
          original_currency = 'UAH',
          fx_date = TO_DATE(month || '-01', 'YYYY-MM-DD')
        WHERE original_limit_cents IS NULL
           OR original_currency IS NULL
           OR fx_date IS NULL
        """
    )

    op.alter_column("budgets", "original_limit_cents", nullable=False)
    op.alter_column("budgets", "original_currency", nullable=False)
    op.alter_column("budgets", "fx_date", nullable=False)

    op.alter_column("budgets", "fx_rate_to_base", server_default=None)


def downgrade():
    # --- budgets ---
    op.drop_column("budgets", "fx_date")
    op.drop_column("budgets", "fx_rate_to_base")
    op.drop_column("budgets", "original_currency")
    op.drop_column("budgets", "original_limit_cents")

    # --- transactions ---
    op.drop_column("transactions", "fx_date")
    op.drop_column("transactions", "fx_rate_to_base")
    op.drop_column("transactions", "original_currency")
    op.drop_column("transactions", "original_amount_cents")

    # --- users ---
    op.drop_column("users", "display_currency")
    op.drop_column("users", "base_currency")
