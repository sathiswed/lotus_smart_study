"""Create the static Class 8 Pilot schema.

Revision ID: 0001_class8_pilot
Revises: None

This revision is intentionally explicit. Later model edits cannot silently
change the schema represented by the first migration.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_class8_pilot"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()

role = sa.Enum("TEACHER", "STUDENT", name="role")
user_status = sa.Enum("ACTIVE", "INACTIVE", name="user_status")
term_code = sa.Enum("TERM_1", "TERM_2", name="term_code")
generation_status = sa.Enum("QUEUED", "GENERATING", "COMPLETED", "FAILED", name="generation_status")
difficulty = sa.Enum("EASY", "MEDIUM", "HARD", "MIXED", name="difficulty")
question_style = sa.Enum("STANDARD", "CBSE_STYLE", "CHALLENGING", name="question_style")
question_type = sa.Enum("MCQ", "ONE_MARK", "TWO_MARK", "THREE_MARK", "FIVE_MARK", "CASE_STUDY", name="question_type")
question_difficulty = sa.Enum("EASY", "MEDIUM", "HARD", "MIXED", name="question_difficulty")
question_style_value = sa.Enum("STANDARD", "CBSE_STYLE", "CHALLENGING", name="question_style_value")
question_status = sa.Enum("DRAFT", "APPROVED", "REJECTED", name="question_status")
test_status = sa.Enum("DRAFT", "PUBLISHED", name="test_status")
snapshot_question_type = sa.Enum("MCQ", "ONE_MARK", "TWO_MARK", "THREE_MARK", "FIVE_MARK", "CASE_STUDY", name="snapshot_question_type")
attempt_status = sa.Enum("IN_PROGRESS", "SUBMITTED", "EVALUATION_IN_PROGRESS", "EVALUATED", "RESULT_PUBLISHED", name="attempt_status")
answer_type = sa.Enum("MCQ", "TEXT", "IMAGE", name="answer_type")
image_status = sa.Enum("UPLOADING", "READY", "FAILED", name="image_status")
evaluation_status = sa.Enum("CORRECT", "WRONG", "PARTIAL", name="evaluation_status")
result_status = sa.Enum("DRAFT", "PUBLISHED", name="result_status")


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("login_identifier", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", role, nullable=False),
        sa.Column("status", user_status, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("login_identifier", name="uq_users_login_identifier"),
    )
    op.create_index("ix_users_login_identifier", "users", ["login_identifier"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "student_profiles",
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("class_level", sa.Integer(), nullable=False),
        sa.CheckConstraint("class_level = 8", name="ck_student_class_8"),
    )
    op.create_table(
        "terms",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", term_code, nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.UniqueConstraint("code", name="uq_terms_code"),
        sa.UniqueConstraint("sequence", name="uq_terms_sequence"),
    )
    op.create_table(
        "chapters",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.UniqueConstraint("term_id", "code", name="uq_chapter_term_code"),
    )
    op.create_index("ix_chapters_term_id", "chapters", ["term_id"])
    op.create_table(
        "topics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_code", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("chapter_id", "section_code", name="uq_topic_chapter_section"),
    )
    op.create_index("ix_topics_chapter_id", "topics", ["chapter_id"])
    op.create_index("ix_topics_is_enabled", "topics", ["is_enabled"])

    op.create_table(
        "source_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("topic_id", UUID, sa.ForeignKey("topics.id")),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("ingestion_status", sa.String(30), nullable=False),
        sa.Column("document_metadata", JSONB, nullable=False),
        *timestamps(),
    )
    for column in ("term_id", "chapter_id", "topic_id"):
        op.create_index(f"ix_source_documents_{column}", "source_documents", [column])
    op.create_table(
        "source_chunks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("source_document_id", UUID, sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("topic_id", UUID, sa.ForeignKey("topics.id")),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("index_reference", sa.String(255)),
        sa.UniqueConstraint("source_document_id", "sequence", name="uq_source_chunk_sequence"),
    )
    for column in ("source_document_id", "term_id", "chapter_id", "topic_id"):
        op.create_index(f"ix_source_chunks_{column}", "source_chunks", [column])

    op.create_table(
        "generation_batches",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("teacher_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("topic_id", UUID, sa.ForeignKey("topics.id")),
        sa.Column("counts", JSONB, nullable=False),
        sa.Column("difficulty", difficulty, nullable=False),
        sa.Column("style", question_style, nullable=False),
        sa.Column("calculated_marks", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(80)),
        sa.Column("model", sa.String(120)),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("index_version", sa.String(80)),
        sa.Column("status", generation_status, nullable=False),
        sa.Column("failure_reason", sa.Text()),
        *timestamps(),
    )
    for column in ("teacher_id", "term_id", "chapter_id", "topic_id", "status"):
        op.create_index(f"ix_generation_batches_{column}", "generation_batches", [column])
    op.create_table(
        "questions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("batch_id", UUID, sa.ForeignKey("generation_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("replaces_question_id", UUID, sa.ForeignKey("questions.id")),
        sa.Column("type", question_type, nullable=False),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", JSONB),
        sa.Column("correct_option_id", sa.String(80)),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("difficulty", question_difficulty, nullable=False),
        sa.Column("style", question_style_value, nullable=False),
        sa.Column("term_id", UUID, sa.ForeignKey("terms.id"), nullable=False),
        sa.Column("chapter_id", UUID, sa.ForeignKey("chapters.id"), nullable=False),
        sa.Column("topic_id", UUID, sa.ForeignKey("topics.id")),
        sa.Column("status", question_status, nullable=False),
        sa.Column("source_trace", JSONB, nullable=False),
        sa.Column("validation_flags", JSONB, nullable=False),
        *timestamps(),
        sa.CheckConstraint("marks > 0", name="ck_question_marks_positive"),
    )
    for column in ("batch_id", "type", "term_id", "chapter_id", "topic_id", "status"):
        op.create_index(f"ix_questions_{column}", "questions", [column])

    op.create_table(
        "tests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("teacher_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("generation_batch_id", UUID, sa.ForeignKey("generation_batches.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("total_marks", sa.Integer(), nullable=False),
        sa.Column("status", test_status, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("total_marks >= 0", name="ck_test_total_nonnegative"),
    )
    op.create_index("ix_tests_teacher_id", "tests", ["teacher_id"])
    op.create_index("ix_tests_status", "tests", ["status"])
    op.create_index("ix_tests_teacher_status", "tests", ["teacher_id", "status"])
    op.create_table(
        "test_questions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("test_id", UUID, sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", UUID, sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("type", snapshot_question_type, nullable=False),
        sa.Column("marks", sa.Integer(), nullable=False),
        sa.Column("options", JSONB),
        sa.Column("correct_option_id", sa.String(80)),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("term_label", sa.String(80), nullable=False),
        sa.Column("chapter_label", sa.String(255), nullable=False),
        sa.Column("topic_label", sa.String(255)),
        sa.UniqueConstraint("test_id", "order", name="uq_test_question_order"),
        sa.UniqueConstraint("test_id", "question_id", name="uq_test_question_source"),
    )
    op.create_index("ix_test_questions_test_id", "test_questions", ["test_id"])
    op.create_table(
        "test_assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("test_id", UUID, sa.ForeignKey("tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("test_id", "student_id", name="uq_test_student_assignment"),
    )
    op.create_index("ix_test_assignments_test_id", "test_assignments", ["test_id"])
    op.create_index("ix_test_assignments_student_id", "test_assignments", ["student_id"])
    op.create_table(
        "attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("test_id", UUID, sa.ForeignKey("tests.id"), nullable=False),
        sa.Column("student_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", attempt_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.UniqueConstraint("test_id", "student_id", name="uq_attempt_test_student"),
    )
    op.create_index("ix_attempts_test_id", "attempts", ["test_id"])
    op.create_index("ix_attempts_student_id", "attempts", ["student_id"])
    op.create_index("ix_attempts_status", "attempts", ["status"])
    op.create_index("ix_attempts_student_status", "attempts", ["student_id", "status"])
    op.create_index("ix_attempts_test_status", "attempts", ["test_id", "status"])
    op.create_table(
        "student_answers",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("attempt_id", UUID, sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_question_id", UUID, sa.ForeignKey("test_questions.id"), nullable=False),
        sa.Column("answer_type", answer_type, nullable=False),
        sa.Column("selected_option_id", sa.String(80)),
        sa.Column("text_answer", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("attempt_id", "test_question_id", name="uq_answer_attempt_question"),
        sa.CheckConstraint("selected_option_id IS NULL OR text_answer IS NULL", name="ck_answer_single_value"),
        sa.CheckConstraint("version > 0", name="ck_answer_version_positive"),
    )
    op.create_index("ix_student_answers_attempt_id", "student_answers", ["attempt_id"])
    op.create_index("ix_student_answers_test_question_id", "student_answers", ["test_question_id"])
    op.create_table(
        "answer_images",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("answer_id", UUID, sa.ForeignKey("student_answers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64)),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("page_order", sa.Integer(), nullable=False),
        sa.Column("status", image_status, nullable=False),
        *timestamps(),
        sa.UniqueConstraint("object_key", name="uq_answer_image_object_key"),
    )
    op.create_index("ix_answer_images_answer_id", "answer_images", ["answer_id"])
    op.create_index("ix_answer_images_status", "answer_images", ["status"])
    op.create_index("uq_ready_image_order", "answer_images", ["answer_id", "page_order"], unique=True, postgresql_where=sa.text("status = 'READY'"))
    op.create_table(
        "question_evaluations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("attempt_id", UUID, sa.ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_question_id", UUID, sa.ForeignKey("test_questions.id"), nullable=False),
        sa.Column("evaluator_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", evaluation_status, nullable=False),
        sa.Column("awarded_marks", sa.Numeric(8, 2), nullable=False),
        sa.Column("feedback", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("attempt_id", "test_question_id", name="uq_evaluation_attempt_question"),
        sa.CheckConstraint("awarded_marks >= 0", name="ck_evaluation_marks_nonnegative"),
        sa.CheckConstraint("version > 0", name="ck_evaluation_version_positive"),
    )
    for column in ("attempt_id", "test_question_id", "evaluator_id"):
        op.create_index(f"ix_question_evaluations_{column}", "question_evaluations", [column])
    op.create_table(
        "results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("attempt_id", UUID, sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("evaluator_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("awarded_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("percentage", sa.Numeric(6, 2), nullable=False),
        sa.Column("overall_comment", sa.Text()),
        sa.Column("status", result_status, nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("attempt_id", name="uq_results_attempt_id"),
        sa.CheckConstraint("awarded_total >= 0", name="ck_result_awarded_nonnegative"),
        sa.CheckConstraint("max_total > 0", name="ck_result_max_positive"),
        sa.CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_result_percentage_range"),
    )
    op.create_index("ix_results_attempt_id", "results", ["attempt_id"], unique=True)
    op.create_index("ix_results_status", "results", ["status"])


def downgrade() -> None:
    raise RuntimeError("Pilot migrations are forward-only; restore from backup instead")
