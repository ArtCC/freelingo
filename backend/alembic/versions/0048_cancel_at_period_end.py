"""Add cancel_at_period_end column to users

Revision ID: 0048_cancel_at_period_end
Revises: 0047_freemium_trial
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0048_cancel_at_period_end"
down_revision: str | None = "0047_freemium_trial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "cancel_at_period_end")
