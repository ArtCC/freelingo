"""Add the per-user end-of-turn pause used by voice conversation.

Revision ID: 0051_conversation_speech_pause
Revises: 0050_dashboard_banner
"""

import sqlalchemy as sa

from alembic import op

revision = "0051_conversation_speech_pause"
down_revision = "0050_dashboard_banner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "conversation_speech_pause",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "conversation_speech_pause")
