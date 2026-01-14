"""change_budget_month_to_string

Revision ID: a611ac26c2fe
Revises: 8068452c329f
Create Date: 2026-01-14 20:41:30.689302

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a611ac26c2fe'
down_revision: Union[str, None] = '8068452c329f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Змінюємо тип колонки з DATE на VARCHAR(7)
    # Використовуємо ::text для конвертації та to_char для форматування YYYY-MM
    op.execute(
        "ALTER TABLE budgets ALTER COLUMN month TYPE VARCHAR(7) USING to_char(month, 'YYYY-MM')"
    )

def downgrade() -> None:
    # Повернення назад (з VARCHAR назад у DATE)
    # Додаємо '-01', щоб отримати валідну дату YYYY-MM-01
    op.execute(
        "ALTER TABLE budgets ALTER COLUMN month TYPE DATE USING (month || '-01')::date"
    )