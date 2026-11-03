from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from ..config import get_settings
from ..database import SessionLocal
from ..dependencies import DB, Teacher
from ..enums import (
    Difficulty as DbDifficulty,
    GenerationStatus,
    QuestionStatus,
    QuestionStyle,
    QuestionType as DbQuestionType,
    TestStatus,
)
from ..errors import APIError
from ..models import Chapter, Curriculum, GenerationBatch, Question, Subject, Term, Test, TestQuestion, Textbook, Topic
from .contracts import Difficulty, QuestionCounts, QuestionMarks, QuestionType, Style
from .provider import ProviderError, create_provider
from .repository import GenerationRecordNotFound, SqlGenerationRepository
from .retrieval import (
    CurriculumScopeError,
    ExactScopeRetriever,
    SourceContentUnavailableError,
)
from .service import (
    GenerationInProgressError,
    GenerationService,
    calculate_total_marks,
)
from .settings import GenerationSettings
from .validation import GenerationValidationError


router = APIRouter(tags=["generation"])
logger = logging.getLogger(__name__)


class CreateGenerationBatch(BaseModel):
    textbook_id: UUID | None = None
    term_id: UUID | None = None
    chapter_id: UUID
    topic_id: UUID | None = None
    counts: QuestionCounts
    marks: QuestionMarks = Field(default_factory=QuestionMarks)
    difficulty: Difficulty
    style: Style


class UpdateQuestion(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=12000)
    marks: int | None = Field(default=None, gt=0, le=100)
    options: list[dict[str, Any]] | None = None
    correct_option_id: str | None = None
    reference_answer: str | None = Field(default=None, min_length=1, max_length=24000)


def _service(db: DB) -> GenerationService:
    settings = GenerationSettings.from_app_settings(get_settings())
    return GenerationService(
        repository=SqlGenerationRepository(db),
        retriever=ExactScopeRetriever(db),
        provider=create_provider(settings),
        settings=settings,
    )


@router.post("/generation-batches", status_code=201)
async def create_generation_batch(payload: CreateGenerationBatch, db: DB, user: Teacher):
    retriever = ExactScopeRetriever(db)
    chapter = await db.get(Chapter, payload.chapter_id)
    if chapter is None:
        raise APIError(422, "invalid_curriculum_scope", "Chapter not found")
    textbook_id = payload.textbook_id or chapter.textbook_id
    if payload.term_id is not None and payload.term_id != chapter.term_id:
        raise APIError(422, "invalid_curriculum_scope", "Term and chapter ancestry is invalid")
    try:
        scope = await retriever.resolve_scope(textbook_id, payload.chapter_id, payload.topic_id)
    except CurriculumScopeError as exc:
        raise APIError(422, "invalid_curriculum_scope", str(exc)) from exc
    except SourceContentUnavailableError as exc:
        raise APIError(422, "source_content_unavailable", str(exc)) from exc
    counts = payload.counts.model_dump()
    marks = payload.marks.model_dump()
    batch = GenerationBatch(
        teacher_id=user.id,
        curriculum_id=scope.curriculum_id,
        subject_id=scope.subject_id,
        textbook_id=scope.textbook_id,
        term_id=scope.term_id,
        chapter_id=payload.chapter_id,
        topic_id=payload.topic_id,
        counts=counts,
        marks_config=marks,
        difficulty=DbDifficulty(payload.difficulty.value),
        style=QuestionStyle(payload.style.value),
        calculated_marks=calculate_total_marks(counts, marks),
        status=GenerationStatus.QUEUED,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return {**_batch_out(batch, []), **_scope_out(scope)}


@router.get("/generation-batches")
async def list_generation_batches(db: DB, user: Teacher):
    rows = (
        await db.execute(
            select(GenerationBatch, Curriculum, Subject, Textbook, Term, Chapter, Topic)
            .join(Curriculum, Curriculum.id == GenerationBatch.curriculum_id)
            .join(Subject, Subject.id == GenerationBatch.subject_id)
            .join(Textbook, Textbook.id == GenerationBatch.textbook_id)
            .join(Term, Term.id == GenerationBatch.term_id)
            .join(Chapter, Chapter.id == GenerationBatch.chapter_id)
            .outerjoin(
                Topic,
                (Topic.id == GenerationBatch.topic_id)
                & (Topic.chapter_id == Chapter.id),
            )
            .where(GenerationBatch.teacher_id == user.id)
            .order_by(GenerationBatch.created_at.desc())
            .limit(10)
        )
    ).all()
    return {
        "items": [
            {
                "id": batch.id,
                "status": batch.status,
                "calculated_marks": batch.calculated_marks,
                "curriculum_id": curriculum.id,
                "board": curriculum.board,
                "state_code": curriculum.state_code,
                "class_level": curriculum.class_level,
                "subject_id": subject.id,
                "subject_title": subject.title,
                "textbook_id": textbook.id,
                "textbook_title": textbook.title,
                "term_title": term.title,
                "chapter_title": chapter.title,
                "topic_title": topic.title if topic else None,
                "failure_reason": batch.failure_reason,
                "created_at": batch.created_at,
            }
            for batch, curriculum, subject, textbook, term, chapter, topic in rows
        ]
    }


@router.get("/generation-batches/{batch_id}")
async def get_generation_batch(batch_id: UUID, db: DB, user: Teacher):
    batch = await db.scalar(
        select(GenerationBatch).where(
            GenerationBatch.id == batch_id, GenerationBatch.teacher_id == user.id
        )
    )
    if batch is None:
        raise APIError(404, "generation_batch_not_found", "Generation batch not found")
    questions = list(
        (
            await db.scalars(
                select(Question)
                .where(Question.batch_id == batch.id)
                .order_by(Question.created_at)
            )
        ).all()
    )
    replaced_ids = {question.replaces_question_id for question in questions if question.replaces_question_id is not None}
    questions = [question for question in questions if question.id not in replaced_ids]
    return {**_batch_out(batch, questions), **(await _batch_scope_out(db, batch))}


async def _generate_batch_in_background(batch_id: UUID, teacher_id: UUID) -> None:
    async with SessionLocal() as session:
        try:
            await _service(session).generate_claimed_batch(batch_id, teacher_id)
        except Exception as exc:
            # Detailed provider/validation diagnostics are logged by the service.
            # Keep this boundary free of prompts, textbook text, credentials, and PII.
            logger.error(
                "Background question generation ended with an error: batch_id=%s exception_type=%s",
                batch_id,
                type(exc).__name__,
            )


@router.post("/generation-batches/{batch_id}/generate")
async def generate_batch(
    batch_id: UUID,
    background_tasks: BackgroundTasks,
    db: DB,
    user: Teacher,
):
    try:
        service = _service(db)
        claimed = await service.claim_batch(batch_id, user.id)
        if claimed:
            background_tasks.add_task(
                _generate_batch_in_background, batch_id, user.id
            )
    except GenerationRecordNotFound as exc:
        raise APIError(404, "generation_batch_not_found", str(exc)) from exc
    except GenerationInProgressError as exc:
        raise APIError(409, "generation_in_progress", str(exc)) from exc
    except SourceContentUnavailableError as exc:
        raise APIError(422, "source_content_unavailable", str(exc)) from exc
    except GenerationValidationError as exc:
        raise APIError(422, "generated_output_invalid", "Generated questions failed validation", {"flags": exc.flags}) from exc
    except ValueError as exc:
        raise APIError(409, "generation_state_invalid", str(exc)) from exc
    except ProviderError as exc:
        raise APIError(502, "llm_provider_failed", str(exc)) from exc
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            raise APIError(503, "llm_not_configured", str(exc)) from exc
        raise
    return await get_generation_batch(batch_id, db, user)


@router.patch("/questions/{question_id}")
async def update_question(question_id: UUID, payload: UpdateQuestion, db: DB, user: Teacher):
    question = await _owned_question(db, question_id, user.id, lock=True)
    if question.status != QuestionStatus.DRAFT:
        raise APIError(409, "question_not_editable", "Only Draft questions can be edited")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(question, field, value)
    if changes:
        question.source_trace = {
            **(question.source_trace or {}),
            "teacher_modified": True,
            "machine_verified_after_edit": False,
        }
        question.validation_flags = sorted(set((question.validation_flags or []) + ["teacher_modified"]))
    _validate_edited_question(question)
    await db.flush()
    batch = await db.get(GenerationBatch, question.batch_id)
    if batch is not None:
        batch.calculated_marks = int(
            await db.scalar(
                select(func.coalesce(func.sum(Question.marks), 0)).where(
                    Question.batch_id == batch.id,
                    Question.status != QuestionStatus.REJECTED,
                )
            )
            or 0
        )
    await db.commit()
    await db.refresh(question)
    return _question_out(question)


@router.post("/questions/{question_id}/regenerate", status_code=201)
async def regenerate_question(question_id: UUID, db: DB, user: Teacher):
    try:
        new_id = await _service(db).regenerate_question(question_id, user.id)
    except GenerationRecordNotFound as exc:
        raise APIError(404, "question_not_found", str(exc)) from exc
    except SourceContentUnavailableError as exc:
        raise APIError(422, "source_content_unavailable", str(exc)) from exc
    except GenerationValidationError as exc:
        raise APIError(422, "generated_output_invalid", "Replacement failed validation", {"flags": exc.flags}) from exc
    except ValueError as exc:
        raise APIError(409, "question_not_regenerable", str(exc)) from exc
    except ProviderError as exc:
        raise APIError(502, "llm_provider_failed", str(exc)) from exc
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            raise APIError(503, "llm_not_configured", str(exc)) from exc
        raise
    replacement = await _owned_question(db, new_id, user.id)
    return _question_out(replacement)


@router.post("/questions/{question_id}/approve")
async def approve_question(question_id: UUID, db: DB, user: Teacher):
    question = await _owned_question(db, question_id, user.id, lock=True)
    if question.status == QuestionStatus.REJECTED:
        raise APIError(409, "question_rejected", "A Rejected question cannot be approved")
    _validate_edited_question(question)
    question.status = QuestionStatus.APPROVED
    await db.commit()
    await db.refresh(question)
    return _question_out(question)


@router.post("/questions/{question_id}/reject")
async def reject_question(question_id: UUID, db: DB, user: Teacher):
    question = await _owned_question(db, question_id, user.id, lock=True)
    published_use = await db.scalar(
        select(TestQuestion.id)
        .join(Test, Test.id == TestQuestion.test_id)
        .where(
            TestQuestion.question_id == question.id,
            Test.status == TestStatus.PUBLISHED,
        )
        .limit(1)
    )
    if published_use is not None:
        raise APIError(409, "question_published", "A question in a published test cannot be rejected")
    question.status = QuestionStatus.REJECTED
    await db.flush()
    batch = await db.get(GenerationBatch, question.batch_id)
    if batch is not None:
        batch.calculated_marks = int(
            await db.scalar(
                select(func.coalesce(func.sum(Question.marks), 0)).where(
                    Question.batch_id == batch.id,
                    Question.status != QuestionStatus.REJECTED,
                )
            )
            or 0
        )
    await db.commit()
    await db.refresh(question)
    return _question_out(question)


async def _owned_question(
    db: DB,
    question_id: UUID,
    teacher_id: UUID,
    *,
    lock: bool = False,
) -> Question:
    statement = (
        select(Question)
        .join(GenerationBatch, GenerationBatch.id == Question.batch_id)
        .where(Question.id == question_id, GenerationBatch.teacher_id == teacher_id)
    )
    if lock:
        statement = statement.with_for_update(of=Question)
    question = await db.scalar(statement)
    if question is None:
        raise APIError(404, "question_not_found", "Question not found")
    return question


def _validate_edited_question(question: Question) -> None:
    if not question.text.strip() or not question.reference_answer.strip():
        raise APIError(422, "invalid_question", "Question and reference answer are required")
    if question.type == DbQuestionType.MCQ:
        options = question.options or []
        ids = [item.get("id") for item in options]
        if len(options) < 3 or len(ids) != len(set(ids)) or question.correct_option_id not in ids:
            raise APIError(422, "invalid_mcq", "MCQ requires distinct options and one valid intended answer")
    elif question.options or question.correct_option_id:
        raise APIError(422, "invalid_question", "Only MCQs may contain options or a correct option")


def _batch_out(batch: GenerationBatch, questions: list[Question]) -> dict[str, Any]:
    return {
        "id": batch.id,
        "teacher_id": batch.teacher_id,
        "curriculum_id": batch.curriculum_id,
        "subject_id": batch.subject_id,
        "textbook_id": batch.textbook_id,
        "term_id": batch.term_id,
        "chapter_id": batch.chapter_id,
        "topic_id": batch.topic_id,
        "counts": batch.counts,
        "marks": batch.marks_config,
        "difficulty": batch.difficulty,
        "style": batch.style,
        "calculated_marks": batch.calculated_marks,
        "status": batch.status,
        "failure_reason": batch.failure_reason,
        "provider": batch.provider,
        "model": batch.model,
        "prompt_version": batch.prompt_version,
        "created_at": batch.created_at,
        "questions": [_question_out(question) for question in questions],
    }


def _question_out(question: Question) -> dict[str, Any]:
    return {
        "id": question.id,
        "batch_id": question.batch_id,
        "replaces_question_id": question.replaces_question_id,
        "text": question.text,
        "type": question.type,
        "marks": question.marks,
        "options": question.options,
        "correct_option_id": question.correct_option_id,
        "reference_answer": question.reference_answer,
        "difficulty": question.difficulty,
        "style": question.style,
        "textbook_id": question.textbook_id,
        "term_id": question.term_id,
        "chapter_id": question.chapter_id,
        "topic_id": question.topic_id,
        "status": question.status,
        "source_trace": question.source_trace,
        "validation_flags": question.validation_flags,
    }


def _scope_out(scope) -> dict[str, Any]:
    return {
        "board": scope.board,
        "state_code": scope.state_code,
        "class_level": scope.class_level,
        "subject_title": scope.subject_title,
        "textbook_title": scope.textbook_title,
        "term_title": scope.term_title,
        "chapter_title": scope.chapter_title,
        "topic_title": scope.topic_title,
    }


async def _batch_scope_out(db: DB, batch: GenerationBatch) -> dict[str, Any]:
    row = (
        await db.execute(
            select(Curriculum, Subject, Textbook, Term, Chapter, Topic)
            .join(Subject, Subject.curriculum_id == Curriculum.id)
            .join(Textbook, Textbook.subject_id == Subject.id)
            .join(Chapter, Chapter.textbook_id == Textbook.id)
            .join(Term, (Term.id == Chapter.term_id) & (Term.subject_id == Subject.id))
            .outerjoin(
                Topic,
                (Topic.id == batch.topic_id) & (Topic.chapter_id == Chapter.id),
            )
            .where(
                Curriculum.id == batch.curriculum_id,
                Subject.id == batch.subject_id,
                Textbook.id == batch.textbook_id,
                Term.id == batch.term_id,
                Chapter.id == batch.chapter_id,
            )
        )
    ).one_or_none()
    if row is None:
        raise APIError(409, "generation_scope_invalid", "Generation batch curriculum ancestry is invalid")
    curriculum, subject, textbook, term, chapter, topic = row
    if batch.topic_id is not None and topic is None:
        raise APIError(409, "generation_scope_invalid", "Generation batch topic ancestry is invalid")
    return {
        "board": curriculum.board,
        "state_code": curriculum.state_code,
        "class_level": curriculum.class_level,
        "subject_title": subject.title,
        "textbook_title": textbook.title,
        "term_title": term.title,
        "chapter_title": chapter.title,
        "topic_title": topic.title if topic else None,
    }
