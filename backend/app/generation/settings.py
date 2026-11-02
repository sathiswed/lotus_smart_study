from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _nonnegative_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    provider: str
    model: str
    api_key: str | None
    base_url: str
    timeout_seconds: int
    retry_count: int
    max_context_characters: int
    prompt_version: str
    similarity_threshold: float

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("LLM_PROVIDER is required")
        if not self.model.strip():
            raise ValueError("OPENAI_MODEL is required")
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("OPENAI_BASE_URL must be an HTTP(S) URL")
        if self.timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if not 0 <= self.retry_count <= 5:
            raise ValueError("LLM_GENERATION_RETRIES must be between 0 and 5")
        if self.max_context_characters <= 0:
            raise ValueError("LLM_MAX_CONTEXT_CHARACTERS must be positive")
        if not self.prompt_version.strip():
            raise ValueError("LLM_PROMPT_VERSION is required")
        if not 0 < self.similarity_threshold <= 1:
            raise ValueError("LLM_SIMILARITY_THRESHOLD must be in (0, 1]")

    @classmethod
    def from_env(cls) -> "GenerationSettings":
        threshold = float(os.getenv("LLM_SIMILARITY_THRESHOLD", "0.86"))
        if not 0 < threshold <= 1:
            raise ValueError("LLM_SIMILARITY_THRESHOLD must be in (0, 1]")
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai").lower(),
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com").rstrip("/"),
            timeout_seconds=_positive_int("LLM_TIMEOUT_SECONDS", 60),
            retry_count=_nonnegative_int("LLM_GENERATION_RETRIES", 2),
            max_context_characters=_positive_int("LLM_MAX_CONTEXT_CHARACTERS", 48000),
            prompt_version=os.getenv("LLM_PROMPT_VERSION", "multi-curriculum-v1"),
            similarity_threshold=threshold,
        )

    @classmethod
    def from_app_settings(cls, settings: object) -> "GenerationSettings":
        base_url = getattr(settings, "openai_base_url", None) or "https://api.openai.com"
        return cls(
            provider=str(getattr(settings, "llm_provider", "openai")).lower(),
            model=str(getattr(settings, "openai_model", "gpt-5-mini")),
            api_key=getattr(settings, "openai_api_key", None),
            base_url=str(base_url).rstrip("/"),
            timeout_seconds=int(getattr(settings, "llm_timeout_seconds", 90)),
            retry_count=int(getattr(settings, "llm_generation_retries", 2)),
            max_context_characters=int(
                getattr(settings, "llm_max_context_characters", 48000)
            ),
            prompt_version=str(getattr(settings, "llm_prompt_version", "multi-curriculum-v1")),
            similarity_threshold=float(
                getattr(settings, "llm_similarity_threshold", 0.86)
            ),
        )

    def require_provider_credentials(self) -> None:
        if self.provider == "openai" and not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required to generate questions")

    @property
    def responses_url(self) -> str:
        """Resolve the Responses endpoint from either an origin or v1 API base URL."""
        base_url = self.base_url.rstrip("/")
        if base_url.lower().endswith("/v1"):
            return f"{base_url}/responses"
        return f"{base_url}/v1/responses"
