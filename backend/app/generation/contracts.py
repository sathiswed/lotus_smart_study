from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


MAX_QUESTIONS_PER_TYPE = 10
MAX_QUESTIONS_PER_BATCH = 20


class QuestionType(StrEnum):
    MCQ = "mcq"
    ONE_MARK = "one_mark"
    TWO_MARK = "two_mark"
    THREE_MARK = "three_mark"
    FIVE_MARK = "five_mark"
    CASE_STUDY = "case_study"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    MIXED = "mixed"


class Style(StrEnum):
    STANDARD = "standard"
    CBSE_STYLE = "cbse_style"
    CHALLENGING = "challenging"


class QuestionCounts(BaseModel):
    mcq: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0
    one_mark: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0
    two_mark: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0
    three_mark: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0
    five_mark: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0
    case_study: Annotated[int, Field(ge=0, le=MAX_QUESTIONS_PER_TYPE)] = 0

    @model_validator(mode="after")
    def require_at_least_one(self) -> "QuestionCounts":
        total = sum(self.model_dump().values())
        if total <= 0:
            raise ValueError("At least one question is required")
        if total > MAX_QUESTIONS_PER_BATCH:
            raise ValueError(
                f"A generation batch may contain at most {MAX_QUESTIONS_PER_BATCH} questions"
            )
        return self


class QuestionMarks(BaseModel):
    mcq: Annotated[int, Field(gt=0, le=100)] = 1
    one_mark: Annotated[int, Field(gt=0, le=100)] = 1
    two_mark: Annotated[int, Field(gt=0, le=100)] = 2
    three_mark: Annotated[int, Field(gt=0, le=100)] = 3
    five_mark: Annotated[int, Field(gt=0, le=100)] = 5
    case_study: Annotated[int, Field(gt=0, le=100)] = 5


class QuestionSpec(BaseModel):
    question_type: QuestionType
    marks: Annotated[int, Field(gt=0, le=100)]
    difficulty: Difficulty
    style: Style


class SourceExcerpt(BaseModel):
    chunk_id: UUID
    document_id: UUID
    textbook_id: UUID
    term_id: UUID
    chapter_id: UUID
    topic_id: UUID | None = None
    page_start: Annotated[int, Field(ge=1)]
    page_end: Annotated[int, Field(ge=1)]
    content: str


class GeneratedOption(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=1000)


class GeneratedSubquestion(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=40,
        description="Short part label such as a, b, or i.",
    )
    text: str = Field(min_length=1, max_length=4000)
    marks: Annotated[
        int,
        Field(gt=0, le=100, description="Marks allocated to this part."),
    ]
    reference_answer: str = Field(
        min_length=1,
        max_length=12000,
        description="Teacher solution for this part.",
    )


class GeneratedQuestion(BaseModel):
    question_text: str = Field(
        min_length=1,
        max_length=12000,
        description="Parent question stem or instruction, excluding any case-study scenario.",
    )
    question_type: QuestionType
    marks: Annotated[int, Field(gt=0, le=100)]
    options: list[GeneratedOption] = Field(default_factory=list)
    correct_option_id: str | None = None
    case_study_context: str | None = Field(
        default=None,
        max_length=12000,
        description=(
            "Scenario text for case_study questions; null for every other question type."
        ),
    )
    subquestions: list[GeneratedSubquestion] = Field(
        default_factory=list,
        description=(
            "Required linked parts for case_study; optional multipart structure for "
            "three_mark and five_mark; empty for mcq, one_mark, and two_mark. "
            "When present, part marks must sum to the parent marks."
        ),
    )
    reference_answer: str = Field(min_length=1, max_length=24000)
    source_chunk_ids: list[UUID] = Field(min_length=1)
    internal_coverage_note: str = Field(default="", max_length=2000)


class GeneratedQuestionBatch(BaseModel):
    questions: list[GeneratedQuestion]


class GenerationScope(BaseModel):
    curriculum_id: UUID
    board: str
    state_code: str | None = None
    class_level: int = Field(ge=8, le=12)
    subject_id: UUID
    subject_code: str
    subject_title: str
    textbook_id: UUID
    textbook_title: str
    term_id: UUID
    term_title: str
    chapter_id: UUID
    chapter_title: str
    topic_id: UUID | None = None
    topic_title: str | None = None

    @model_validator(mode="after")
    def enforce_exact_scope(self) -> "GenerationScope":
        if self.board not in {"cbse", "state", "icse"}:
            raise ValueError("Unsupported board")
        if self.board == "state" and not self.state_code:
            raise ValueError("State Board scope requires a state identifier")
        if self.board != "state" and self.state_code:
            raise ValueError("State identifier is only valid for State Board")
        if (self.topic_id is None) != (self.topic_title is None):
            raise ValueError("Topic id and title must be supplied together")
        return self


class ProviderRequest(BaseModel):
    scope: GenerationScope
    specs: list[QuestionSpec] = Field(min_length=1)
    excerpts: list[SourceExcerpt] = Field(min_length=1)
    avoid_questions: list[str] = Field(default_factory=list)
    regeneration_source: str | None = None


class ValidatedQuestion(BaseModel):
    question: GeneratedQuestion
    validation_flags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any]
