"""Add the global dashboard banner and per-user dismissal marker.

Revision ID: 0050_dashboard_banner
Revises: 0049_memory_user_content_unique
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0050_dashboard_banner"
down_revision = "0049_memory_user_content_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dashboard_banners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("translations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_locale", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_dashboard_banners_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "users",
        sa.Column("dismissed_dashboard_banner_revision", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "dismissed_dashboard_banner_revision")
    op.drop_table("dashboard_banners")
