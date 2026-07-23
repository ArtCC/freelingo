"""Add freemium trial columns

Revision ID: 0047_freemium_trial
Revises: 0046_feedback_read_states
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0047_freemium_trial"
down_revision: str | None = "0046_feedback_read_states"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "freemium_trial_ends_at",
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "freemium_trial_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "freemium_trial_used")
    op.drop_column("users", "freemium_trial_ends_at")
