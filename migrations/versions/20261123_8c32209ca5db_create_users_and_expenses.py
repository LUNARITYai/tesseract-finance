"""create users and expenses"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from tesseract_finance.models.base import (
    CREATE_UPDATED_AT_FUNCTION,
    UPDATED_AT_FUNCTION,
    create_updated_at_trigger,
    drop_updated_at_trigger,
)

revision: str = "8c32209ca5db"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMPED_TABLES = ("users", "expenses")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="PLN", nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("is_planned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_expenses_amount_positive")),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_expenses_currency_code")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_expenses_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )
    op.create_index(
        "ix_expenses_user_id_date",
        "expenses",
        ["user_id", sa.literal_column("date DESC")],
        unique=False,
    )
    op.execute(CREATE_UPDATED_AT_FUNCTION)
    for table in TIMESTAMPED_TABLES:
        op.execute(create_updated_at_trigger(table))


def downgrade() -> None:
    for table in TIMESTAMPED_TABLES:
        op.execute(drop_updated_at_trigger(table))
    op.drop_index("ix_expenses_user_id_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("users")
    op.execute(f"DROP FUNCTION {UPDATED_AT_FUNCTION}()")
