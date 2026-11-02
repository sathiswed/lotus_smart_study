"""Add shared login throttling state.

Revision ID: 0002_shared_login_throttling
Revises: 0001_class8_pilot
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_shared_login_throttling"
down_revision = "0001_class8_pilot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_throttles",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("failure_count >= 0", name="ck_login_throttle_failure_nonnegative"),
    )
    op.create_index("ix_login_throttles_updated_at", "login_throttles", ["updated_at"])


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
