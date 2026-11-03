"""Add optional student school details.

Revision ID: 0007_student_school_fields
Revises: 0006_bulk_textbook_ingestion
"""

import sqlalchemy as sa
from alembic import op


revision = "0007_student_school_fields"
down_revision = "0006_bulk_textbook_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_profiles", sa.Column("school_name", sa.String(255), nullable=True))
    op.add_column("student_profiles", sa.Column("school_location", sa.String(255), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
