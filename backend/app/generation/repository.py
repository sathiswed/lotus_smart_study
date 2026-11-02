from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import (
    Difficulty as DbDifficulty,
    GenerationStatus,
    QuestionStatus,
    QuestionStyle,
    QuestionType as DbQuestionType,
)
from ..models import Chapter, Curriculum, GenerationBatch, Question, Subject, Term, Textbook, Topic
from .contracts import (
    Difficulty,
    GeneratedQuestion,
    GenerationScope,
    QuestionCounts,
    QuestionMarks,
    QuestionType,
    Style,
)


class GenerationRecordNotFound(LookupError):
    pass


@dataclass(slots=True)
class BatchContext:
    id: UUID
    teacher_id: UUID
    status: str
    counts: QuestionCounts
    marks: QuestionMarks
    difficulty: Difficulty
    style: Style
    scope: GenerationScope


@dataclass(slots=True)
class ExistingQuestion:
    id: UUID
    batch_id: UUID
    question_type: QuestionType
    marks: int
    text: str
    status: str
    scope: GenerationScope


@dataclass(slots=True)
class QuestionDraft:
    question: GeneratedQuestion
    validation_flags: list[str]
    provenance: dict[str, Any]
    replaces_question_id: UUID | None = None


class SqlGenerationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_batch(self, batch_id: UUID, teacher_id: UUID) -> BatchContext:
        row = (
            await self.session.execute(
                select(GenerationBatch, Curriculum, Subject, Textbook, Term, Chapter, Topic)
                .join(Textbook, Textbook.id == GenerationBatch.textbook_id)
                .join(Subject, Subject.id == Textbook.subject_id)
                .join(Curriculum, Curriculum.id == Subject.curriculum_id)
                .join(Term, Term.id == GenerationBatch.term_id)
                .join(Chapter, Chapter.id == GenerationBatch.chapter_id)
                .outerjoin(
                    Topic,
                    (Topic.id == GenerationBatch.topic_id)
                    & (Topic.chapter_id == Chapter.id),
                )
                .where(
                    GenerationBatch.id == batch_id,
                    GenerationBatch.teacher_id == teacher_id,
                    GenerationBatch.curriculum_id == Curriculum.id,
                    GenerationBatch.subject_id == Subject.id,
                    GenerationBatch.textbook_id == Textbook.id,
                    GenerationBatch.term_id == Term.id,
                    GenerationBatch.chapter_id == Chapter.id,
                )
            )
        ).one_or_none()
        if row is None:
            raise GenerationRecordNotFound("Generation batch not found")
        batch, curriculum, subject, textbook, term, chapter, topic = row
        if batch.topic_id is not None and topic is None:
            raise ValueError("Generation batch topic ancestry is invalid")
        if topic is not None and not topic.is_enabled:
            raise ValueError("Generation batch refers to a disabled topic")
        return BatchContext(
            id=batch.id,
            teacher_id=batch.teacher_id,
            status=batch.status.value,
            counts=QuestionCounts.model_validate(batch.counts),
            marks=QuestionMarks.model_validate(batch.marks_config),
            difficulty=Difficulty(batch.difficulty.value),
            style=Style(batch.style.value),
            scope=GenerationScope(
                curriculum_id=curriculum.id,
                board=curriculum.board,
                state_code=curriculum.state_code,
                class_level=curriculum.class_level,
                subject_id=subject.id,
                subject_code=subject.code,
                subject_title=subject.title,
                textbook_id=textbook.id,
                textbook_title=textbook.title,
                term_id=term.id,
                term_title=term.title,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                topic_id=topic.id if topic else None,
                topic_title=topic.title if topic else None,
            ),
        )

    async def mark_generating(
        self, batch_id: UUID, provider: str, model: str, prompt_version: str
    ) -> None:
        batch = await self.session.scalar(
            select(GenerationBatch)
            .where(GenerationBatch.id == batch_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if batch is None:
            raise GenerationRecordNotFound("Generation batch not found")
        if batch.status == GenerationStatus.GENERATING:
            raise ValueError("Generation batch is already running")
        if batch.status == GenerationStatus.COMPLETED:
            raise ValueError("Generation batch is already complete")
        if batch.status not in {GenerationStatus.QUEUED, GenerationStatus.FAILED}:
            raise ValueError(f"Batch cannot generate from status {batch.status.value}")
        batch.status = GenerationStatus.GENERATING
        batch.failure_reason = None
        batch.provider = provider
        batch.model = model
        batch.prompt_version = prompt_version
        # Commit the claim before the provider call so concurrent requests observe
        # the Generating state rather than creating a second question set.
        await self.session.commit()

    async def recent_question_texts(
        self, batch: BatchContext, limit: int = 100
    ) -> list[str]:
        statement = (
            select(Question.text)
            .join(GenerationBatch, GenerationBatch.id == Question.batch_id)
            .where(
                GenerationBatch.teacher_id == batch.teacher_id,
                Question.term_id == batch.scope.term_id,
                Question.chapter_id == batch.scope.chapter_id,
                Question.textbook_id == batch.scope.textbook_id,
            )
            .order_by(Question.created_at.desc())
            .limit(limit)
        )
        if batch.scope.topic_id is not None:
            statement = statement.where(Question.topic_id == batch.scope.topic_id)
        return list((await self.session.scalars(statement)).all())

    async def save_batch_questions(
        self, batch: BatchContext, drafts: list[QuestionDraft], *, commit: bool = True
    ) -> list[UUID]:
        records: list[Question] = []
        for draft in drafts:
            question = draft.question
            record = Question(
                batch_id=batch.id,
                replaces_question_id=draft.replaces_question_id,
                type=DbQuestionType(question.question_type.value),
                marks=question.marks,
                text=_combined_question_text(question),
                options=[item.model_dump(mode="json") for item in question.options] or None,
                correct_option_id=question.correct_option_id,
                reference_answer=_combined_reference_answer(question),
                difficulty=DbDifficulty(batch.difficulty.value),
                style=QuestionStyle(batch.style.value),
                textbook_id=batch.scope.textbook_id,
                term_id=batch.scope.term_id,
                chapter_id=batch.scope.chapter_id,
                topic_id=batch.scope.topic_id,
                status=QuestionStatus.DRAFT,
                source_trace=draft.provenance,
                validation_flags=draft.validation_flags,
            )
            self.session.add(record)
            records.append(record)
        db_batch = await self.session.get(GenerationBatch, batch.id)
        if db_batch is None:
            raise GenerationRecordNotFound("Generation batch not found")
        db_batch.status = GenerationStatus.COMPLETED
        db_batch.failure_reason = None
        await self.session.flush()
        if commit:
            await self.session.commit()
            for record in records:
                await self.session.refresh(record)
        return [record.id for record in records]

    async def fail_batch(self, batch_id: UUID, reason: str) -> None:
        batch = await self.session.get(GenerationBatch, batch_id)
        if batch is not None:
            batch.status = GenerationStatus.FAILED
            batch.failure_reason = reason[:2000]
            await self.session.commit()

    async def list_batch_question_ids(self, batch_id: UUID) -> list[UUID]:
        return list(
            (
                await self.session.scalars(
                    select(Question.id)
                    .where(Question.batch_id == batch_id)
                    .order_by(Question.created_at)
                )
            ).all()
        )

    async def get_question(
        self, question_id: UUID, teacher_id: UUID, *, lock: bool = False
    ) -> ExistingQuestion:
        statement = (
                select(Question, GenerationBatch, Curriculum, Subject, Textbook, Term, Chapter, Topic)
                .join(GenerationBatch, GenerationBatch.id == Question.batch_id)
                .join(Textbook, Textbook.id == Question.textbook_id)
                .join(Subject, Subject.id == Textbook.subject_id)
                .join(Curriculum, Curriculum.id == Subject.curriculum_id)
                .join(Term, Term.id == Question.term_id)
                .join(Chapter, Chapter.id == Question.chapter_id)
                .outerjoin(
                    Topic,
                    (Topic.id == Question.topic_id)
                    & (Topic.chapter_id == Chapter.id),
                )
                .where(
                    Question.id == question_id,
                    GenerationBatch.teacher_id == teacher_id,
                    GenerationBatch.curriculum_id == Curriculum.id,
                    GenerationBatch.subject_id == Subject.id,
                    GenerationBatch.textbook_id == Textbook.id,
                    Question.textbook_id == Textbook.id,
                    Question.term_id == Term.id,
                    Question.chapter_id == Chapter.id,
                )
            )
        if lock:
            statement = statement.with_for_update(of=Question)
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            raise GenerationRecordNotFound("Question not found")
        question, _batch, curriculum, subject, textbook, term, chapter, topic = row
        if question.topic_id is not None and topic is None:
            raise ValueError("Question topic ancestry is invalid")
        return ExistingQuestion(
            id=question.id,
            batch_id=question.batch_id,
            question_type=QuestionType(question.type.value),
            marks=question.marks,
            text=question.text,
            status=question.status.value,
            scope=GenerationScope(
                curriculum_id=curriculum.id,
                board=curriculum.board,
                state_code=curriculum.state_code,
                class_level=curriculum.class_level,
                subject_id=subject.id,
                subject_code=subject.code,
                subject_title=subject.title,
                textbook_id=textbook.id,
                textbook_title=textbook.title,
                term_id=term.id,
                term_title=term.title,
                chapter_id=chapter.id,
                chapter_title=chapter.title,
                topic_id=topic.id if topic else None,
                topic_title=topic.title if topic else None,
            ),
        )

    async def replace_question(
        self, batch: BatchContext, original: ExistingQuestion, draft: QuestionDraft
    ) -> UUID:
        draft.replaces_question_id = original.id
        new_ids = await self.save_batch_questions(batch, [draft], commit=False)
        original_record = await self.session.get(Question, original.id)
        if original_record is not None:
            original_record.status = QuestionStatus.REJECTED
        await self.session.flush()
        db_batch = await self.session.get(GenerationBatch, batch.id)
        if db_batch is not None:
            db_batch.calculated_marks = int(
                await self.session.scalar(
                    select(func.coalesce(func.sum(Question.marks), 0)).where(
                        Question.batch_id == batch.id,
                        Question.status != QuestionStatus.REJECTED,
                    )
                )
                or 0
            )
        # Commit the replacement and rejection together so the row lock held by
        # get_question(lock=True) cannot expose an intermediate Draft state.
        await self.session.commit()
        return new_ids[0]

    async def has_replacement(self, question_id: UUID) -> bool:
        return (
            await self.session.scalar(
                select(Question.id)
                .where(Question.replaces_question_id == question_id)
                .limit(1)
            )
        ) is not None


def _combined_reference_answer(question: GeneratedQuestion) -> str:
    if not question.subquestions:
        return question.reference_answer
    details = "\n\n".join(
        f"{item.id} ({item.marks} marks): {item.reference_answer}"
        for item in question.subquestions
    )
    return f"{question.reference_answer}\n\n{details}"


def _combined_question_text(question: GeneratedQuestion) -> str:
    parts: list[str] = []
    if question.question_type == QuestionType.CASE_STUDY:
        parts.append(question.case_study_context or question.question_text)
    else:
        parts.append(question.question_text)
    if question.question_text and question.question_text not in parts:
        parts.append(question.question_text)
    parts.extend(f"{item.id}. {item.text} ({item.marks} marks)" for item in question.subquestions)
    return "\n\n".join(parts)
