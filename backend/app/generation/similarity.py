from __future__ import annotations

import re
from difflib import SequenceMatcher


_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?(?:/\d+)?")
_SPACE_PATTERN = re.compile(r"\s+")
_PUNCTUATION_PATTERN = re.compile(r"[^a-z0-9<> ]+")


def normalize_question(text: str, *, mask_numbers: bool = False) -> str:
    normalized = text.casefold()
    if mask_numbers:
        normalized = _NUMBER_PATTERN.sub(" <number> ", normalized)
    normalized = _PUNCTUATION_PATTERN.sub(" ", normalized)
    return _SPACE_PATTERN.sub(" ", normalized).strip()


def similarity(left: str, right: str, *, mask_numbers: bool = False) -> float:
    return SequenceMatcher(
        None,
        normalize_question(left, mask_numbers=mask_numbers),
        normalize_question(right, mask_numbers=mask_numbers),
    ).ratio()


def is_near_duplicate(candidate: str, existing: str, threshold: float) -> bool:
    return similarity(candidate, existing) >= threshold


def is_number_only_change(candidate: str, previous: str, threshold: float = 0.96) -> bool:
    if normalize_question(candidate) == normalize_question(previous):
        return True
    return similarity(candidate, previous, mask_numbers=True) >= threshold


def duplicate_flags(
    candidate: str,
    prior_questions: list[str],
    threshold: float,
    regeneration_source: str | None = None,
) -> list[str]:
    flags: list[str] = []
    if any(is_near_duplicate(candidate, prior, threshold) for prior in prior_questions):
        flags.append("near_duplicate")
    if regeneration_source and is_number_only_change(candidate, regeneration_source):
        flags.append("number_only_variation")
    return flags
