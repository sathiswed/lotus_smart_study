from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from .contracts import (
    Difficulty,
    ProviderRequest,
    QuestionSpec,
    QuestionType,
)
from .provider import LLMProvider, ProviderError
from .repository import QuestionDraft, SqlGenerationRepository
from .retrieval import ExactScopeRetriever
from .settings import GenerationSettings
from .validation import (
    GenerationValidationError,
    reject_blocking_flags,
    validate_batch_shape,
    validate_question,
)


QUESTION_MARKS: dict[QuestionType, int] = {
    QuestionType.MCQ: 1,
    QuestionType.ONE_MARK: 1,
    QuestionType.TWO_MARK: 2,
    QuestionType.THREE_MARK: 3,
    QuestionType.FIVE_MARK: 5,
    # Defaults preserve the existing pattern; every batch may override them.
    QuestionType.CASE_STUDY: 5,
}


logger = logging.getLogger(__name__)


class GenerationInProgressError(RuntimeError):
    pass


@dataclass(slots=True)
class GenerationService:
    repository: SqlGenerationRepository
    retriever: ExactScopeRetriever
    provider: LLMProvider
    settings: GenerationSettings

    async def claim_batch(self, batch_id: UUID, teacher_id: UUID) -> bool:
        batch = await self.repository.get_batch(batch_id, teacher_id)
        if batch.status == "completed":
            return False
        if batch.status == "generating":
            maximum_run_seconds = (
                (self.settings.retry_count + 1) * self.settings.timeout_seconds
            ) + 60
            updated_at = batch.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            age_seconds = (datetime.now(UTC) - updated_at).total_seconds()
            if age_seconds <= maximum_run_seconds:
                return False
            logger.warning(
                "Recovering stale question generation batch: batch_id=%s age_seconds=%d",
                batch.id,
                int(age_seconds),
            )
            await self.repository.fail_batch(
                batch.id,
                "Generation was interrupted before completion and may be retried.",
            )
            batch = await self.repository.get_batch(batch_id, teacher_id)
        if batch.status not in {"queued", "failed"}:
            raise ValueError(f"Batch cannot generate from status {batch.status}")

        try:
            await self.repository.mark_generating(
                batch.id,
                self.provider.provider_name,
                self.provider.model_name,
                self.settings.prompt_version,
            )
        except ValueError:
            current = await self.repository.get_batch(batch_id, teacher_id)
            if current.status in {"generating", "completed"}:
                return False
            raise
        return True

    async def generate_claimed_batch(
        self, batch_id: UUID, teacher_id: UUID
    ) -> list[UUID]:
        batch = await self.repository.get_batch(batch_id, teacher_id)
        if batch.status == "completed":
            return await self.repository.list_batch_question_ids(batch.id)
        if batch.status != "generating":
            raise ValueError(f"Claimed batch has invalid status {batch.status}")
        try:
            excerpts = await self.retriever.retrieve(batch.scope)
            prior = await self.repository.recent_question_texts(batch)
            specs = _expand_specs(batch.counts.model_dump(), batch.marks.model_dump(), batch.difficulty, batch.style)
            request = ProviderRequest(
                scope=batch.scope,
                specs=specs,
                excerpts=excerpts,
                avoid_questions=prior,
            )
            drafts = await self._generate_validated(request)
            return await self.repository.save_batch_questions(batch, drafts)
        except Exception as exc:
            await self.repository.fail_batch(batch.id, _safe_failure_reason(exc))
            raise

    async def generate_batch(self, batch_id: UUID, teacher_id: UUID) -> list[UUID]:
        claimed = await self.claim_batch(batch_id, teacher_id)
        if not claimed:
            batch = await self.repository.get_batch(batch_id, teacher_id)
            if batch.status == "completed":
                return await self.repository.list_batch_question_ids(batch.id)
            raise GenerationInProgressError("Generation batch is already running")
        return await self.generate_claimed_batch(batch_id, teacher_id)

    async def regenerate_question(
        self, question_id: UUID, teacher_id: UUID
    ) -> UUID:
        # Hold a row lock through replacement generation. This is intentionally
        # conservative for the small pilot and prevents duplicate replacements.
        original = await self.repository.get_question(question_id, teacher_id, lock=True)
        if original.status not in {"draft", "rejected"}:
            raise ValueError("Only a Draft or Rejected question can be regenerated")
        if await self.repository.has_replacement(original.id):
            raise ValueError("This question already has a replacement")
        batch = await self.repository.get_batch(original.batch_id, teacher_id)
        excerpts = await self.retriever.retrieve(original.scope, original.text)
        prior = await self.repository.recent_question_texts(batch)
        request = ProviderRequest(
            scope=original.scope,
            specs=[
                QuestionSpec(
                    question_type=original.question_type,
                    marks=original.marks,
                    difficulty=batch.difficulty,
                    style=batch.style,
                )
            ],
            excerpts=excerpts,
            avoid_questions=prior,
            regeneration_source=original.text,
        )
        drafts = await self._generate_validated(request)
        return await self.repository.replace_question(batch, original, drafts[0])

    async def _generate_validated(self, request: ProviderRequest) -> list[QuestionDraft]:
        last_validation_error: GenerationValidationError | None = None
        last_provider_error: ProviderError | None = None
        total_attempts = self.settings.retry_count + 1
        for attempt_index in range(1, total_attempts + 1):
            try:
                generated = await self.provider.generate(request)
            except ProviderError as exc:
                last_provider_error = exc
                logger.warning(
                    "Question generation provider attempt %d/%d failed: "
                    "exception_type=%s status_code=%s request_id=%s validation_errors=%s",
                    attempt_index,
                    total_attempts,
                    exc.exception_type or type(exc).__name__,
                    exc.status_code if exc.status_code is not None else "unavailable",
                    exc.request_id or "unavailable",
                    ",".join(exc.validation_errors) or "none",
                )
                continue
            batch_flags = validate_batch_shape(generated.questions, request.specs)
            if batch_flags:
                last_validation_error = GenerationValidationError(batch_flags)
                _log_validation_failure(
                    attempt_index, total_attempts, last_validation_error.flags
                )
                continue

            drafts: list[QuestionDraft] = []
            blocking: list[str] = []
            in_batch_text: list[str] = []
            for question, spec in zip(generated.questions, request.specs, strict=True):
                flags = validate_question(
                    question,
                    spec,
                    request.excerpts,
                    [*request.avoid_questions, *in_batch_text],
                    self.settings.similarity_threshold,
                    request.regeneration_source,
                )
                if flags:
                    blocking.extend(flags)
                in_batch_text.append(question.question_text)
                drafts.append(
                    QuestionDraft(
                        question=question,
                        validation_flags=flags,
                        provenance={
                            "curriculum_id": str(request.scope.curriculum_id),
                            "board": request.scope.board,
                            "state_code": request.scope.state_code,
                            "class_level": request.scope.class_level,
                            "subject_id": str(request.scope.subject_id),
                            "subject": request.scope.subject_code,
                            "textbook_id": str(request.scope.textbook_id),
                            "textbook_title": request.scope.textbook_title,
                            "term_id": str(request.scope.term_id),
                            "chapter_id": str(request.scope.chapter_id),
                            "topic_id": str(request.scope.topic_id)
                            if request.scope.topic_id
                            else None,
                            "source_chunk_ids": [str(value) for value in question.source_chunk_ids],
                            "provider": self.provider.provider_name,
                            "model": self.provider.model_name,
                            "prompt_version": self.settings.prompt_version,
                            "authoritative_pattern_corpus_used": False,
                        },
                    )
                )
            if not blocking:
                return drafts
            last_validation_error = GenerationValidationError(blocking)
            _log_validation_failure(
                attempt_index, total_attempts, last_validation_error.flags
            )

        if last_validation_error:
            reject_blocking_flags(last_validation_error.flags)
        if last_provider_error:
            raise ProviderError(
                "Question provider failed after the configured total attempt budget",
                exception_type=last_provider_error.exception_type,
                status_code=last_provider_error.status_code,
                request_id=last_provider_error.request_id,
                validation_errors=last_provider_error.validation_errors,
            ) from last_provider_error
        raise GenerationValidationError(["unknown_generation_validation_failure"])


def _expand_specs(counts: dict[str, int], marks: dict[str, int], difficulty: Difficulty, style) -> list[QuestionSpec]:
    specs: list[QuestionSpec] = []
    for value in QuestionType:
        for _ in range(counts.get(value.value, 0)):
            specs.append(
                QuestionSpec(
                    question_type=value,
                    marks=marks.get(value.value, QUESTION_MARKS[value]),
                    difficulty=difficulty,
                    style=style,
                )
            )
    return specs


def calculate_total_marks(counts: dict[str, int], marks: dict[str, int] | None = None) -> int:
    configured = marks or {value.value: QUESTION_MARKS[value] for value in QuestionType}
    return sum(counts.get(value.value, 0) * configured.get(value.value, QUESTION_MARKS[value]) for value in QuestionType)


def _safe_failure_reason(exc: Exception) -> str:
    if isinstance(exc, GenerationValidationError):
        return f"Generated output failed validation: {', '.join(exc.flags)}"
    return f"Generation failed: {type(exc).__name__}"


def _log_validation_failure(
    attempt_index: int, total_attempts: int, flags: list[str]
) -> None:
    logger.warning(
        "Question generation validation attempt %d/%d failed: validation_errors=%s",
        attempt_index,
        total_attempts,
        ",".join(sorted(set(flags))) or "unknown_validation_failure",
    )
