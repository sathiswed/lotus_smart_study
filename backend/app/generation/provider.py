from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from .contracts import GeneratedQuestionBatch, ProviderRequest
from .prompts import SYSTEM_PROMPT, build_user_prompt, output_json_schema
from .settings import GenerationSettings


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        exception_type: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.exception_type = exception_type
        self.status_code = status_code
        self.request_id = request_id
        self.validation_errors = validation_errors or []


class LLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def generate(self, request: ProviderRequest) -> GeneratedQuestionBatch: ...


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: GenerationSettings) -> None:
        self.settings = settings

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.settings.model

    async def generate(self, request: ProviderRequest) -> GeneratedQuestionBatch:
        self.settings.require_provider_credentials()
        body = {
            "model": self.settings.model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(
                        request, self.settings.max_context_characters
                    ),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "textbook_question_batch",
                    "schema": output_json_schema(),
                    "strict": True,
                }
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        response: httpx.Response | None = None
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(
                    self.settings.responses_url, headers=headers, json=body
                )
            response.raise_for_status()
            payload = response.json()
            output_text = self._extract_output_text(payload)
            return GeneratedQuestionBatch.model_validate_json(output_text)
        except ProviderError as exc:
            raise ProviderError(
                str(exc),
                exception_type=exc.exception_type or type(exc).__name__,
                status_code=exc.status_code or _response_status(response),
                request_id=exc.request_id or _response_request_id(response),
                validation_errors=exc.validation_errors,
            ) from exc
        except ValidationError as exc:
            raise ProviderError(
                "Question provider returned structured output that failed schema validation",
                exception_type=type(exc).__name__,
                status_code=_response_status(response),
                request_id=_response_request_id(response),
                validation_errors=_safe_validation_errors(exc),
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, json.JSONDecodeError) as exc:
            # The generation service owns the single shared attempt budget so
            # transport and validation retries cannot multiply each other.
            raise ProviderError(
                "Question provider request failed",
                exception_type=type(exc).__name__,
                status_code=_exception_status(exc) or _response_status(response),
                request_id=_exception_request_id(exc) or _response_request_id(response),
            ) from exc

    @staticmethod
    def _extract_output_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, str):
                        return text
        raise ProviderError("Provider response did not contain structured output text")


def _response_status(response: httpx.Response | None) -> int | None:
    return response.status_code if response is not None else None


def _response_request_id(response: httpx.Response | None) -> str | None:
    if response is None:
        return None
    return response.headers.get("x-request-id") or response.headers.get(
        "openai-request-id"
    )


def _exception_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def _exception_request_id(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    return _response_request_id(response) if isinstance(response, httpx.Response) else None


def _safe_validation_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for item in exc.errors(
        include_url=False, include_context=False, include_input=False
    ):
        location = ".".join(str(part) for part in item.get("loc", ())) or "response"
        errors.append(f"{location}:{item.get('type', 'validation_error')}")
    return sorted(set(errors))


def create_provider(settings: GenerationSettings | None = None) -> LLMProvider:
    resolved = settings or GenerationSettings.from_env()
    if resolved.provider == "openai":
        return OpenAIProvider(resolved)
    raise ValueError(f"Unsupported LLM_PROVIDER: {resolved.provider}")
