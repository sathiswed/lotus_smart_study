from __future__ import annotations

from collections import Counter
from uuid import UUID

from .contracts import GeneratedQuestion, QuestionSpec, QuestionType, SourceExcerpt
from .similarity import duplicate_flags


MULTIPART_QUESTION_TYPES = {QuestionType.THREE_MARK, QuestionType.FIVE_MARK}


class GenerationValidationError(ValueError):
    def __init__(self, flags: list[str]) -> None:
        self.flags = sorted(set(flags))
        super().__init__(", ".join(self.flags))


def validate_question(
    question: GeneratedQuestion,
    spec: QuestionSpec,
    excerpts: list[SourceExcerpt],
    prior_questions: list[str],
    similarity_threshold: float,
    regeneration_source: str | None = None,
) -> list[str]:
    flags: list[str] = []
    available_chunk_ids: set[UUID] = {excerpt.chunk_id for excerpt in excerpts}

    if question.question_type != spec.question_type:
        flags.append("question_type_mismatch")
    if question.marks != spec.marks:
        flags.append("marks_mismatch")
    if not set(question.source_chunk_ids).issubset(available_chunk_ids):
        flags.append("invalid_source_trace")

    if question.question_type == QuestionType.MCQ:
        option_ids = [option.id for option in question.options]
        option_text = [option.text.casefold().strip() for option in question.options]
        if len(question.options) < 3:
            flags.append("mcq_too_few_options")
        if len(option_ids) != len(set(option_ids)):
            flags.append("mcq_duplicate_option_ids")
        if len(option_text) != len(set(option_text)):
            flags.append("mcq_duplicate_option_text")
        if not question.correct_option_id or question.correct_option_id not in option_ids:
            flags.append("mcq_invalid_correct_option")
        if question.case_study_context or question.subquestions:
            flags.append("mcq_unexpected_case_study_fields")
    else:
        if question.options or question.correct_option_id:
            flags.append("non_mcq_contains_options")

    if question.question_type == QuestionType.CASE_STUDY:
        if not question.case_study_context:
            flags.append("case_study_missing_context")
        if not question.subquestions:
            flags.append("case_study_missing_subquestions")
        elif sum(item.marks for item in question.subquestions) != question.marks:
            flags.append("case_study_marks_mismatch")
    else:
        if question.question_type != QuestionType.MCQ:
            if question.case_study_context:
                flags.append("non_case_study_contains_context")
            if question.subquestions:
                if question.question_type not in MULTIPART_QUESTION_TYPES:
                    flags.append("multipart_not_allowed_for_question_type")
                else:
                    if len(question.subquestions) < 2:
                        flags.append("multipart_requires_multiple_parts")
                    if sum(item.marks for item in question.subquestions) != question.marks:
                        flags.append("multipart_marks_mismatch")

    flags.extend(
        duplicate_flags(
            question.question_text,
            prior_questions,
            similarity_threshold,
            regeneration_source,
        )
    )
    return sorted(set(flags))


def validate_batch_shape(
    questions: list[GeneratedQuestion], specs: list[QuestionSpec]
) -> list[str]:
    flags: list[str] = []
    if len(questions) != len(specs):
        flags.append("question_count_mismatch")
    expected = Counter((spec.question_type, spec.marks) for spec in specs)
    actual = Counter((question.question_type, question.marks) for question in questions)
    if expected != actual:
        flags.append("question_spec_distribution_mismatch")
    return flags


def reject_blocking_flags(flags: list[str]) -> None:
    if flags:
        raise GenerationValidationError(flags)
