"""add fx fields to budget

Revision ID: 8068452c329f
Revises: f5d0a1e9b4ee
Create Date: 2026-01-14 19:34:35.837455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8068452c329f'
down_revision: Union[str, None] = 'f5d0a1e9b4ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column("budgets", sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="UAH"))

    # backfill:
    # - старі бюджети: вважай, що original = base (бо інакше ти не відновиш)
    op.execute("""
        UPDATE budgets
        SET original_limit_cents = limit_cents,
            original_currency = COALESCE(currency, base_currency, 'UAH'),
            fx_rate_to_base = 1.0,
            fx_date = CURRENT_DATE
        WHERE original_limit_cents IS NULL
    """)

    op.alter_column("budgets", "original_limit_cents", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("budgets", "original_currency", existing_type=sa.String(length=8), nullable=False, server_default="UAH")
    op.alter_column("budgets", "fx_rate_to_base", existing_type=sa.Numeric(20, 8), nullable=False, server_default="1.0")
    op.alter_column("budgets", "fx_date", existing_type=sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE"))

def downgrade():
    op.drop_column("budgets", "fx_date")
    op.drop_column("budgets", "fx_rate_to_base")
    op.drop_column("budgets", "original_currency")
    op.drop_column("budgets", "original_limit_cents")
    op.drop_column("budgets", "base_currency")
