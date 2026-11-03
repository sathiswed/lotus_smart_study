"""Add bulk textbook files and reviewable chapter ingestion.

Revision ID: 0006_bulk_textbook_ingestion
Revises: 0005_multi_curriculum
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0006_bulk_textbook_ingestion"
down_revision = "0005_multi_curriculum"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "textbook_files",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("textbook_id", UUID, sa.ForeignKey("textbooks.id"), nullable=False),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64)),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'uploading'")),
        sa.Column("detected_chapters", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("approved_chapters", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("object_key", name="uq_textbook_file_object_key"),
        sa.UniqueConstraint("textbook_id", "term_id", "checksum", name="uq_textbook_file_checksum"),
        sa.CheckConstraint("byte_size > 0", name="ck_textbook_file_size_positive"),
        sa.CheckConstraint("page_count IS NULL OR page_count > 0", name="ck_textbook_file_pages_positive"),
    )
    op.create_index("ix_textbook_files_textbook_id", "textbook_files", ["textbook_id"])
    op.create_index("ix_textbook_files_term_id", "textbook_files", ["term_id"])
    op.create_index("ix_textbook_files_status", "textbook_files", ["status"])
    op.create_index("ix_textbook_files_created_by", "textbook_files", ["created_by"])

    op.add_column("source_documents", sa.Column("textbook_file_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_source_documents_textbook_file",
        "source_documents",
        "textbook_files",
        ["textbook_file_id"],
        ["id"],
    )
    op.create_index("ix_source_documents_textbook_file_id", "source_documents", ["textbook_file_id"])
    op.create_index(
        "uq_source_document_file_chapter",
        "source_documents",
        ["textbook_file_id", "chapter_id"],
        unique=True,
        postgresql_where=sa.text("textbook_file_id IS NOT NULL"),
    )

    op.drop_constraint("uq_chapter_term_code", "chapters", type_="unique")
    op.create_unique_constraint(
        "uq_chapter_textbook_term_code",
        "chapters",
        ["textbook_id", "term_id", "code"],
    )


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
