from __future__ import annotations

import json

from .contracts import ProviderRequest


SYSTEM_PROMPT = """You create draft assessment questions for teacher review within the explicitly supplied board, state curriculum, class, subject, textbook, and chapter scope.
The supplied textbook excerpts are the absolute content boundary. Do not use concepts not supported by them.
Never mix content from another board, state curriculum, class, subject, textbook, or chapter.
The style label is a framing preference only; do not claim that an authoritative board-pattern corpus was used.
Create materially different reasoning, framing, context, or direction. Changing only numbers is invalid.
Return teacher reference answers, but never evaluate a student's work or award student marks.
Follow the requested question type and marks exactly.
MCQ, one_mark, and two_mark questions must be single-part: return an empty subquestions array and null case_study_context. For MCQs, include plausible distinct options and exactly one intended answer.
Three_mark and five_mark questions may be single-part or genuinely multipart. When multipart, provide at least two subquestions, allocate positive marks to every part, and make the part marks sum exactly to the parent marks. Keep case_study_context null.
Case_study questions must contain a coherent scenario in case_study_context and one or more related subquestions whose marks sum exactly to the parent marks.
For every multipart or case-study question, provide both the overall teacher reference answer and a reference answer for every subquestion.
Every question must cite one or more supplied source_chunk_ids. Return only the required JSON structure."""


def build_user_prompt(request: ProviderRequest, max_context_characters: int) -> str:
    excerpts: list[dict[str, object]] = []
    consumed = 0
    for excerpt in request.excerpts:
        remaining = max_context_characters - consumed
        if remaining <= 0:
            break
        content = excerpt.content[:remaining]
        consumed += len(content)
        excerpts.append(
            {
                "source_chunk_id": str(excerpt.chunk_id),
                "pages": [excerpt.page_start, excerpt.page_end],
                "content": content,
            }
        )

    payload = {
        "scope": request.scope.model_dump(mode="json"),
        "requested_questions": [spec.model_dump(mode="json") for spec in request.specs],
        "textbook_excerpts": excerpts,
        "avoid_near_duplicates_of": request.avoid_questions[-40:],
        "regeneration_instruction": (
            "Replace the prior question while preserving scope, type, and marks. "
            "Change the reasoning path or framing, not only numeric values."
            if request.regeneration_source
            else None
        ),
        "prior_question_to_replace": request.regeneration_source,
    }
    return json.dumps(payload, ensure_ascii=False)


def output_json_schema() -> dict[str, object]:
    # OpenAI strict Structured Outputs requires every object property to be
    # required and every object to reject additional properties. Pydantic's
    # normal schema intentionally treats fields with defaults as optional, so
    # normalize the complete schema tree before sending it to the provider.
    from .contracts import GeneratedQuestionBatch

    schema = GeneratedQuestionBatch.model_json_schema()
    return _strict_object_schema(schema)


def _strict_object_schema(value):
    if isinstance(value, list):
        return [_strict_object_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized = {
        key: _strict_object_schema(item)
        for key, item in value.items()
        if key != "default"
    }
    if normalized.get("type") == "object":
        properties = normalized.get("properties", {})
        normalized["additionalProperties"] = False
        normalized["required"] = list(properties)
    return normalized
