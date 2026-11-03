import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import (
    AnswerType, AttemptStatus, Difficulty, EvaluationStatus, GenerationStatus, ImageStatus,
    QuestionStatus, QuestionStyle, QuestionType, ResultStatus, Role, TestStatus, UserStatus,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    login_identifier: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(Enum(Role, name="role"), index=True)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus, name="user_status"), default=UserStatus.ACTIVE, index=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship()


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    __table_args__ = (CheckConstraint("failure_count >= 0", name="ck_login_throttle_failure_nonnegative"),)
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Curriculum(TimestampMixin, Base):
    __tablename__ = "curricula"
    __table_args__ = (
        UniqueConstraint("board", "state_code", "class_level", name="uq_curriculum_board_state_class"),
        CheckConstraint("board IN ('cbse', 'state', 'icse')", name="ck_curriculum_board"),
        CheckConstraint("class_level BETWEEN 8 AND 12", name="ck_curriculum_class_8_12"),
        CheckConstraint(
            "(board = 'state' AND state_code IS NOT NULL AND state_code <> '') OR "
            "(board <> 'state' AND state_code IS NULL)",
            name="ck_curriculum_state_scope",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    board: Mapped[str] = mapped_column(String(20), index=True)
    state_code: Mapped[str | None] = mapped_column(String(80), index=True)
    class_level: Mapped[int] = mapped_column(Integer, index=True)


class Subject(TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("curriculum_id", "code", name="uq_subject_curriculum_code"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id"), index=True)
    code: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(160))
    curriculum: Mapped[Curriculum] = relationship()


class Textbook(TimestampMixin, Base):
    __tablename__ = "textbooks"
    __table_args__ = (UniqueConstraint("subject_id", "title", "edition", name="uq_textbook_subject_title_edition"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    academic_year: Mapped[str | None] = mapped_column(String(40))
    edition: Mapped[str] = mapped_column(String(80), default="current", server_default=text("'current'"))
    object_key: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64))
    processing_status: Mapped[str] = mapped_column(String(30), default="pending_upload", index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    subject: Mapped[Subject] = relationship()


class TextbookFile(TimestampMixin, Base):
    __tablename__ = "textbook_files"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_textbook_file_object_key"),
        UniqueConstraint("textbook_id", "term_id", "checksum", name="uq_textbook_file_checksum"),
        CheckConstraint("byte_size > 0", name="ck_textbook_file_size_positive"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="ck_textbook_file_pages_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="uploading", index=True)
    detected_chapters: Mapped[list] = mapped_column(JSONB, default=list)
    approved_chapters: Mapped[list] = mapped_column(JSONB, default=list)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        CheckConstraint("class_level BETWEEN 8 AND 12", name="ck_student_class_8_12"),
        Index(
            "uq_student_profiles_email_normalized",
            func.lower(text("email")),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id"), index=True)
    class_level: Mapped[int] = mapped_column(Integer, default=8)
    email: Mapped[str | None] = mapped_column(String(320))
    mobile: Mapped[str | None] = mapped_column(String(32))
    user: Mapped[User] = relationship()


class Term(Base):
    __tablename__ = "terms"
    __table_args__ = (
        UniqueConstraint("subject_id", "code", name="uq_term_subject_code"),
        UniqueConstraint("subject_id", "sequence", name="uq_term_subject_sequence"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    # A free normalized code supports annual, semester, and board-specific
    # groupings while retaining the existing term_1 / term_2 values.
    code: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer)


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("textbook_id", "term_id", "code", name="uq_chapter_textbook_term_code"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    sequence: Mapped[int] = mapped_column(Integer)
    term: Mapped[Term] = relationship()


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("chapter_id", "section_code", name="uq_topic_chapter_section"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), index=True)
    section_code: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(255))
    sequence: Mapped[int] = mapped_column(Integer)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    chapter: Mapped[Chapter] = relationship()


class SourceDocument(TimestampMixin, Base):
    __tablename__ = "source_documents"
    __table_args__ = (
        Index(
            "uq_source_document_file_chapter",
            "textbook_file_id",
            "chapter_id",
            unique=True,
            postgresql_where=text("textbook_file_id IS NOT NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    textbook_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("textbook_files.id"), index=True)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"), index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(80), default="1")
    ingestion_status: Mapped[str] = mapped_column(String(30), default="pending")
    document_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_document_id", "sequence", name="uq_source_chunk_sequence"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"), index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    index_reference: Mapped[str | None] = mapped_column(String(255))


class GenerationBatch(TimestampMixin, Base):
    __tablename__ = "generation_batches"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"), index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    counts: Mapped[dict] = mapped_column(JSONB)
    marks_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="difficulty"))
    style: Mapped[QuestionStyle] = mapped_column(Enum(QuestionStyle, name="question_style"))
    calculated_marks: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    index_version: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[GenerationStatus] = mapped_column(Enum(GenerationStatus, name="generation_status"), default=GenerationStatus.QUEUED, index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    questions: Mapped[list["Question"]] = relationship(back_populates="batch")


class Question(TimestampMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (CheckConstraint("marks > 0", name="ck_question_marks_positive"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_batches.id", ondelete="CASCADE"), index=True)
    replaces_question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id"))
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="question_type"), index=True)
    marks: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSONB)
    correct_option_id: Mapped[str | None] = mapped_column(String(80))
    reference_answer: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="question_difficulty"))
    style: Mapped[QuestionStyle] = mapped_column(Enum(QuestionStyle, name="question_style_value"))
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("terms.id"), index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chapters.id"), index=True)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topics.id"), index=True)
    status: Mapped[QuestionStatus] = mapped_column(Enum(QuestionStatus, name="question_status"), default=QuestionStatus.DRAFT, index=True)
    source_trace: Mapped[dict] = mapped_column(JSONB, default=dict)
    validation_flags: Mapped[list] = mapped_column(JSONB, default=list)
    batch: Mapped[GenerationBatch] = relationship(back_populates="questions")


class Test(TimestampMixin, Base):
    __tablename__ = "tests"
    __table_args__ = (CheckConstraint("total_marks >= 0", name="ck_test_total_nonnegative"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    generation_batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("generation_batches.id"))
    curriculum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("curricula.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), index=True)
    textbook_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("textbooks.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str] = mapped_column(Text, default="")
    total_marks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[TestStatus] = mapped_column(Enum(TestStatus, name="test_status"), default=TestStatus.DRAFT, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TestQuestion(Base):
    __tablename__ = "test_questions"
    __table_args__ = (UniqueConstraint("test_id", "order", name="uq_test_question_order"), UniqueConstraint("test_id", "question_id", name="uq_test_question_source"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    order: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, name="snapshot_question_type"))
    marks: Mapped[int] = mapped_column(Integer)
    options: Mapped[list | None] = mapped_column(JSONB)
    correct_option_id: Mapped[str | None] = mapped_column(String(80))
    reference_answer: Mapped[str] = mapped_column(Text)
    board_label: Mapped[str] = mapped_column(String(120))
    class_level: Mapped[int] = mapped_column(Integer)
    subject_label: Mapped[str] = mapped_column(String(160))
    textbook_label: Mapped[str] = mapped_column(String(255))
    term_label: Mapped[str] = mapped_column(String(80))
    chapter_label: Mapped[str] = mapped_column(String(255))
    topic_label: Mapped[str | None] = mapped_column(String(255))


class TestAssignment(Base):
    __tablename__ = "test_assignments"
    __table_args__ = (UniqueConstraint("test_id", "student_id", name="uq_test_student_assignment"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Attempt(TimestampMixin, Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("test_id", "student_id", name="uq_attempt_test_student"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[AttemptStatus] = mapped_column(Enum(AttemptStatus, name="attempt_status"), default=AttemptStatus.IN_PROGRESS, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentAnswer(TimestampMixin, Base):
    __tablename__ = "student_answers"
    __table_args__ = (
        UniqueConstraint("attempt_id", "test_question_id", name="uq_answer_attempt_question"),
        CheckConstraint("selected_option_id IS NULL OR text_answer IS NULL", name="ck_answer_single_value"),
        CheckConstraint("version > 0", name="ck_answer_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    test_question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_questions.id"), index=True)
    answer_type: Mapped[AnswerType] = mapped_column(Enum(AnswerType, name="answer_type"))
    selected_option_id: Mapped[str | None] = mapped_column(String(80))
    text_answer: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AnswerImage(TimestampMixin, Base):
    __tablename__ = "answer_images"
    __table_args__ = (UniqueConstraint("object_key", name="uq_answer_image_object_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_answers.id", ondelete="CASCADE"), index=True)
    object_key: Mapped[str] = mapped_column(Text)
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(80))
    byte_size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(64))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    page_order: Mapped[int] = mapped_column(Integer)
    status: Mapped[ImageStatus] = mapped_column(Enum(ImageStatus, name="image_status"), default=ImageStatus.UPLOADING, index=True)


class QuestionEvaluation(TimestampMixin, Base):
    __tablename__ = "question_evaluations"
    __table_args__ = (
        UniqueConstraint("attempt_id", "test_question_id", name="uq_evaluation_attempt_question"),
        CheckConstraint("awarded_marks >= 0", name="ck_evaluation_marks_nonnegative"),
        CheckConstraint("version > 0", name="ck_evaluation_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), index=True)
    test_question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_questions.id"), index=True)
    evaluator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[EvaluationStatus] = mapped_column(Enum(EvaluationStatus, name="evaluation_status"))
    awarded_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    feedback: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (
        CheckConstraint("awarded_total >= 0", name="ck_result_awarded_nonnegative"),
        CheckConstraint("max_total > 0", name="ck_result_max_positive"),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="ck_result_percentage_range"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id"), unique=True, index=True)
    evaluator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    awarded_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    percentage: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    overall_comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ResultStatus] = mapped_column(Enum(ResultStatus, name="result_status"), default=ResultStatus.DRAFT, index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index("ix_tests_teacher_status", Test.teacher_id, Test.status)
Index("ix_attempts_student_status", Attempt.student_id, Attempt.status)
Index("ix_attempts_test_status", Attempt.test_id, Attempt.status)
Index("uq_ready_image_order", AnswerImage.answer_id, AnswerImage.page_order, unique=True, postgresql_where=text("status = 'READY'"))
