from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "Lotus Smart Study API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://lotus:lotus@localhost:5432/lotus_smart_study"
    frontend_origin: str = "http://localhost:3000"

    session_cookie_name: str = "lotus_session"
    session_secret: str = Field(default="change-me-before-use", min_length=16)
    session_hours: int = 8
    cookie_secure: bool = False
    login_max_failures: int = 5
    login_failure_window_seconds: int = 300

    short_answer_max_chars: int = 4000
    image_max_bytes: int = 10 * 1024 * 1024
    image_max_pages: int = 10
    image_max_pixels: int = 20_000_000
    image_max_dimension: int = 3000
    image_quality: int = 88
    textbook_max_bytes: int = 100 * 1024 * 1024

    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_bucket: str = "lotus-smart-study-private"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_signed_url_seconds: int = 900

    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    openai_base_url: str | None = None
    llm_timeout_seconds: int = 90
    llm_generation_retries: int = 2
    llm_max_context_characters: int = 48000
    llm_prompt_version: str = "multi-curriculum-v1"
    llm_similarity_threshold: float = 0.86

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.is_production and (
            self.session_secret == "change-me-before-use"
            or self.session_secret.startswith("replace-with-")
        ):
            raise ValueError("SESSION_SECRET must be changed in production")
        if self.image_quality < 1 or self.image_quality > 100:
            raise ValueError("IMAGE_QUALITY must be between 1 and 100")
        if self.textbook_max_bytes < 1:
            raise ValueError("TEXTBOOK_MAX_BYTES must be positive")
        if self.login_max_failures < 1:
            raise ValueError("LOGIN_MAX_FAILURES must be at least 1")
        if self.login_failure_window_seconds < 1:
            raise ValueError("LOGIN_FAILURE_WINDOW_SECONDS must be at least 1")
        if self.llm_timeout_seconds <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        if not 0 <= self.llm_generation_retries <= 5:
            raise ValueError("LLM_GENERATION_RETRIES must be between 0 and 5")
        if self.llm_max_context_characters <= 0:
            raise ValueError("LLM_MAX_CONTEXT_CHARACTERS must be positive")
        if not 0 < self.llm_similarity_threshold <= 1:
            raise ValueError("LLM_SIMILARITY_THRESHOLD must be in (0, 1]")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
