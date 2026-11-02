"""Add optional Class 8 student contact details.

Revision ID: 0003_student_management
Revises: 0002_shared_login_throttling
"""

import sqlalchemy as sa
from alembic import op


revision = "0003_student_management"
down_revision = "0002_shared_login_throttling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_profiles", sa.Column("email", sa.String(320), nullable=True)
    )
    op.add_column(
        "student_profiles", sa.Column("mobile", sa.String(32), nullable=True)
    )
    # Preserve every existing account and relationship while ensuring older
    # student rows have the Class 8 profile expected by management queries.
    op.execute(
        sa.text(
            """
            INSERT INTO student_profiles (user_id, class_level, email, mobile)
            SELECT users.id, 8, NULL, NULL
            FROM users
            WHERE users.role = 'STUDENT'
              AND NOT EXISTS (
                  SELECT 1 FROM student_profiles
                  WHERE student_profiles.user_id = users.id
              )
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
