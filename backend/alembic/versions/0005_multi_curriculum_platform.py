"""Add multi-board, multi-class curriculum and textbook ownership.

Revision ID: 0005_multi_curriculum
Revises: 0004_student_email_auth
"""

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0005_multi_curriculum"
down_revision = "0004_student_email_auth"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
CBSE_8_CURRICULUM_ID = "10000000-0000-4000-8000-000000000001"
CBSE_8_MATH_SUBJECT_ID = "10000000-0000-4000-8000-000000000002"
GANITA_PRAKASH_ID = "10000000-0000-4000-8000-000000000003"
DEFAULT_MARKS_CONFIG = {
    "mcq": 1,
    "one_mark": 1,
    "two_mark": 2,
    "three_mark": 3,
    "five_mark": 5,
    "case_study": 5,
}
# Keep whitespace after each JSON name separator. SQLAlchemy's text() parser
# otherwise interprets compact JSON such as `"mcq":1` as a `:1` bind token,
# which renders as NULL in Alembic's generated DDL.
DEFAULT_MARKS_CONFIG_JSON = json.dumps(DEFAULT_MARKS_CONFIG, separators=(",", ": "))


def upgrade() -> None:
    op.create_table(
        "curricula",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("board", sa.String(20), nullable=False),
        sa.Column("state_code", sa.String(80)),
        sa.Column("class_level", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code", name="uq_curricula_code"),
        sa.UniqueConstraint("board", "state_code", "class_level", name="uq_curriculum_board_state_class"),
        sa.CheckConstraint("board IN ('cbse', 'state', 'icse')", name="ck_curriculum_board"),
        sa.CheckConstraint("class_level BETWEEN 8 AND 12", name="ck_curriculum_class_8_12"),
        sa.CheckConstraint("(board = 'state' AND state_code IS NOT NULL AND state_code <> '') OR (board <> 'state' AND state_code IS NULL)", name="ck_curriculum_state_scope"),
    )
    op.create_index("ix_curricula_code", "curricula", ["code"], unique=True)
    op.create_index("ix_curricula_board", "curricula", ["board"])
    op.create_index("ix_curricula_state_code", "curricula", ["state_code"])
    op.create_index("ix_curricula_class_level", "curricula", ["class_level"])

    op.create_table(
        "subjects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("curriculum_id", UUID, sa.ForeignKey("curricula.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("curriculum_id", "code", name="uq_subject_curriculum_code"),
    )
    op.create_index("ix_subjects_curriculum_id", "subjects", ["curriculum_id"])

    op.create_table(
        "textbooks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("subject_id", UUID, sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("academic_year", sa.String(40)),
        sa.Column("edition", sa.String(80), nullable=False, server_default=sa.text("'current'")),
        sa.Column("object_key", sa.Text()),
        sa.Column("checksum", sa.String(64)),
        sa.Column("processing_status", sa.String(30), nullable=False, server_default=sa.text("'pending_upload'")),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("subject_id", "title", "edition", name="uq_textbook_subject_title_edition"),
    )
    op.create_index("ix_textbooks_subject_id", "textbooks", ["subject_id"])
    op.create_index("ix_textbooks_processing_status", "textbooks", ["processing_status"])
    op.create_index("ix_textbooks_created_by", "textbooks", ["created_by"])

    op.execute(sa.text(f"""
        INSERT INTO curricula (id, code, board, state_code, class_level)
        VALUES ('{CBSE_8_CURRICULUM_ID}', 'cbse-8', 'cbse', NULL, 8)
    """))
    op.execute(sa.text(f"""
        INSERT INTO subjects (id, curriculum_id, code, title)
        VALUES ('{CBSE_8_MATH_SUBJECT_ID}', '{CBSE_8_CURRICULUM_ID}', 'mathematics', 'Mathematics')
    """))
    op.execute(sa.text(f"""
        INSERT INTO textbooks (id, subject_id, title, edition, processing_status)
        VALUES ('{GANITA_PRAKASH_ID}', '{CBSE_8_MATH_SUBJECT_ID}', 'Ganita Prakash', 'existing-pilot', 'ready')
    """))

    op.add_column("student_profiles", sa.Column("curriculum_id", UUID, nullable=True))
    op.execute(sa.text(f"UPDATE student_profiles SET curriculum_id = '{CBSE_8_CURRICULUM_ID}'"))
    op.alter_column("student_profiles", "curriculum_id", nullable=False)
    op.create_foreign_key("fk_student_profiles_curriculum", "student_profiles", "curricula", ["curriculum_id"], ["id"])
    op.create_index("ix_student_profiles_curriculum_id", "student_profiles", ["curriculum_id"])
    op.drop_constraint("ck_student_class_8", "student_profiles", type_="check")
    op.create_check_constraint("ck_student_class_8_12", "student_profiles", "class_level BETWEEN 8 AND 12")

    op.add_column("terms", sa.Column("subject_id", UUID, nullable=True))
    op.execute(sa.text(f"UPDATE terms SET subject_id = '{CBSE_8_MATH_SUBJECT_ID}'"))
    op.alter_column("terms", "subject_id", nullable=False)
    op.create_foreign_key("fk_terms_subject", "terms", "subjects", ["subject_id"], ["id"])
    op.create_index("ix_terms_subject_id", "terms", ["subject_id"])
    op.drop_constraint("uq_terms_code", "terms", type_="unique")
    op.drop_constraint("uq_terms_sequence", "terms", type_="unique")
    op.create_unique_constraint("uq_term_subject_code", "terms", ["subject_id", "code"])
    op.create_unique_constraint("uq_term_subject_sequence", "terms", ["subject_id", "sequence"])
    # Preserve existing term_1 / term_2 values while permitting annual,
    # semester, and board-specific syllabus groupings.
    op.execute("ALTER TABLE terms ALTER COLUMN code TYPE VARCHAR(50) USING lower(code::text)")
    op.execute("DROP TYPE term_code")

    _add_owned_textbook_column("chapters")
    _add_owned_textbook_column("source_documents")
    _add_owned_textbook_column("source_chunks")
    _add_owned_textbook_column("generation_batches")
    _add_owned_textbook_column("questions")
    for name, target, value in (
        ("curriculum_id", "curricula", CBSE_8_CURRICULUM_ID),
        ("subject_id", "subjects", CBSE_8_MATH_SUBJECT_ID),
    ):
        op.add_column("generation_batches", sa.Column(name, UUID, nullable=True))
        op.execute(sa.text(f"UPDATE generation_batches SET {name} = '{value}'"))
        op.alter_column("generation_batches", name, nullable=False)
        op.create_foreign_key(f"fk_generation_batches_{name}", "generation_batches", target, [name], ["id"])
        op.create_index(f"ix_generation_batches_{name}", "generation_batches", [name])
    op.add_column(
        "generation_batches",
        sa.Column(
            "marks_config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text(f"'{DEFAULT_MARKS_CONFIG_JSON}'::jsonb"),
        ),
    )

    for name, target in (("curriculum_id", "curricula"), ("subject_id", "subjects"), ("textbook_id", "textbooks")):
        op.add_column("tests", sa.Column(name, UUID, nullable=True))
        op.create_foreign_key(f"fk_tests_{name}", "tests", target, [name], ["id"])
        op.create_index(f"ix_tests_{name}", "tests", [name])
    op.execute(sa.text(f"""
        UPDATE tests SET
          curriculum_id = '{CBSE_8_CURRICULUM_ID}',
          subject_id = '{CBSE_8_MATH_SUBJECT_ID}',
          textbook_id = '{GANITA_PRAKASH_ID}'
    """))
    for name in ("curriculum_id", "subject_id", "textbook_id"):
        op.alter_column("tests", name, nullable=False)

    snapshot_columns = (
        sa.Column("board_label", sa.String(120), nullable=True),
        sa.Column("class_level", sa.Integer(), nullable=True),
        sa.Column("subject_label", sa.String(160), nullable=True),
        sa.Column("textbook_label", sa.String(255), nullable=True),
    )
    for column in snapshot_columns:
        op.add_column("test_questions", column)
    op.execute(sa.text("""
        UPDATE test_questions SET board_label = 'CBSE', class_level = 8,
          subject_label = 'Mathematics', textbook_label = 'Ganita Prakash'
    """))
    for name in ("board_label", "class_level", "subject_label", "textbook_label"):
        op.alter_column("test_questions", name, nullable=False)


def _add_owned_textbook_column(table_name: str) -> None:
    op.add_column(table_name, sa.Column("textbook_id", UUID, nullable=True))
    op.execute(sa.text(f"UPDATE {table_name} SET textbook_id = '{GANITA_PRAKASH_ID}'"))
    op.alter_column(table_name, "textbook_id", nullable=False)
    op.create_foreign_key(f"fk_{table_name}_textbook", table_name, "textbooks", ["textbook_id"], ["id"])
    op.create_index(f"ix_{table_name}_textbook_id", table_name, ["textbook_id"])


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
