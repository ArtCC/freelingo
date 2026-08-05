"""Enforce globally unique memory content per user.

Revision ID: 0049_memory_user_content_unique
Revises: 0048_cancel_at_period_end
"""

from alembic import op

revision = "0049_memory_user_content_unique"
down_revision = "0048_cancel_at_period_end"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM memories newer
        USING memories older
        WHERE newer.user_id = older.user_id
          AND newer.content = older.content
          AND newer.id > older.id
        """)
    op.create_unique_constraint(
        "uq_memories_user_content",
        "memories",
        ["user_id", "content"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_memories_user_content", "memories", type_="unique")
