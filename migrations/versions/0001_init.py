"""init

Revision ID: 0001_init
Revises:
Create Date: 2025-12-30
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("external_auth_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Kyiv"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "type", "name", name="uq_categories_user_type_name"),
    )
    op.create_index("ix_categories_user_type_arch_pos", "categories", ["user_id", "type", "is_archived", "position"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.SmallInteger(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("payment_method", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("client_ref", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "client_ref", name="uq_tx_user_client_ref"),
    )
    op.create_index("ix_tx_user_occurred_id_desc", "transactions", ["user_id", "occurred_at", "id"])
    op.create_index("ix_tx_user_type_occurred_desc", "transactions", ["user_id", "type", "occurred_at"])
    op.create_index("ix_tx_user_category_occurred_desc", "transactions", ["user_id", "category_id", "occurred_at"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("category_id", sa.Uuid(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("limit_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="UAH"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "month", "category_id", name="uq_budget_user_month_category"),
    )
    op.create_index("ix_budget_user_month_desc", "budgets", ["user_id", "month"])


def downgrade():
    op.drop_index("ix_budget_user_month_desc", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("ix_tx_user_category_occurred_desc", table_name="transactions")
    op.drop_index("ix_tx_user_type_occurred_desc", table_name="transactions")
    op.drop_index("ix_tx_user_occurred_id_desc", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_categories_user_type_arch_pos", table_name="categories")
    op.drop_table("categories")

    op.drop_table("users")
