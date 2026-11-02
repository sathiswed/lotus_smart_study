"""Use student email logins and require temporary-password changes.

Revision ID: 0004_student_email_auth
Revises: 0003_student_management
"""

import sqlalchemy as sa
from alembic import op


revision = "0004_student_email_auth"
down_revision = "0003_student_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "login_identifier",
        existing_type=sa.String(255),
        type_=sa.String(320),
        existing_nullable=False,
    )
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Email remains nullable so legacy accounts are preserved without invented
    # values. Any existing case-insensitive duplicates must be resolved by the
    # owner before applying this migration; no account data is rewritten here.
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_student_profiles_email_normalized
            ON student_profiles (lower(email))
            WHERE email IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
