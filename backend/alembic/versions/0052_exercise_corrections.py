"""Add the corrections column for free-write exercise evaluations.

Revision ID: 0052_exercise_corrections
Revises: 0051_conversation_speech_pause
"""

import sqlalchemy as sa

from alembic import op

revision = "0052_exercise_corrections"
down_revision = "0051_conversation_speech_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column("corrections", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exercises", "corrections")
