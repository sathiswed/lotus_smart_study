"""Textbook-grounded question generation across configured curricula."""

from .provider import LLMProvider, OpenAIProvider, create_provider
from .service import GenerationService

__all__ = ["GenerationService", "LLMProvider", "OpenAIProvider", "create_provider"]
