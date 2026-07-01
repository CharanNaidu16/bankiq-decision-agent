"""Runtime configuration for the Enterprise Decision Analysis Agent backend.

All operator-tunable settings (API keys, model id, host/port, CORS origins) are
loaded here from environment variables / a ``.env`` file via pydantic-settings.
Domain constants that are intrinsic to the business live in ``constants.py``.

A single cached :func:`get_settings` accessor is exposed so the rest of the
application never re-reads the environment or constructs more than one
``Settings`` instance.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Absolute path to the ``backend`` directory (this file lives in backend/app/).
BACKEND_ROOT_DIR: Path = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR: Path = BACKEND_ROOT_DIR / "data"


class Settings(BaseSettings):
    """Strongly-typed application settings sourced from the environment.

    Attributes:
        groq_api_key: Groq Cloud API key. When empty, the pipeline runs in a
            degraded, template-only mode instead of raising.
        groq_model: Groq model id used by every agent.
        groq_base_url: OpenAI-compatible base URL for the Groq API.
        llm_temperature: Sampling temperature for agent reasoning.
        llm_request_timeout_seconds: Per-request LLM timeout.
        host: Bind host for the FastAPI server.
        port: Bind port for the FastAPI server.
        cors_allowed_origins: Origins permitted to call the API from a browser.
        data_dir: Directory containing the seven generated CSV datasets.
    """

    model_config = SettingsConfigDict(
        # Read from a project-root .env or a backend/.env, whichever exists.
        env_file=(BACKEND_ROOT_DIR.parent / ".env", BACKEND_ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL"
    )

    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE", ge=0.0, le=2.0)
    llm_request_timeout_seconds: float = Field(
        default=60.0, alias="LLM_REQUEST_TIMEOUT_SECONDS", gt=0.0
    )
    # Reasoning/"thinking" effort, sent only when non-empty. Needed for Gemini
    # thinking models (e.g. gemini-2.5-flash), which otherwise spend the output
    # token budget on internal reasoning and truncate the JSON answer. Set to
    # "none" for those models; leave blank for Groq's non-reasoning llama models.
    llm_reasoning_effort: str = Field(default="", alias="LLM_REASONING_EFFORT")

    # Outbound email (used by the "Email report" action). For Gmail, smtp_username
    # is the Gmail address and smtp_password is a 16-character App Password.
    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT", gt=0, lt=65536)
    smtp_username: str = Field(default="", alias="SMTP_USERNAME")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_name: str = Field(default="Enterprise Decision Analysis Agent", alias="SMTP_FROM_NAME")
    smtp_timeout_seconds: float = Field(
        default=30.0, alias="SMTP_TIMEOUT_SECONDS", gt=0.0
    )

    host: str = Field(default="127.0.0.1", alias="BANKIQ_HOST")
    port: int = Field(default=8000, alias="BANKIQ_PORT", gt=0, lt=65536)

    # NoDecode prevents pydantic-settings from JSON-decoding this list before the
    # validator below splits the comma-separated string from the environment.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="CORS_ALLOWED_ORIGINS",
    )

    data_dir: Path = Field(default=DEFAULT_DATA_DIR, alias="BANKIQ_DATA_DIR")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_comma_separated_origins(cls, raw_value: object) -> object:
        """Allow CORS origins to be supplied as a comma-separated string.

        Args:
            raw_value: The raw value read from the environment. May be a list
                (already parsed) or a comma-separated string.

        Returns:
            A list of trimmed origin strings, or the value unchanged when it is
            not a string.
        """
        if isinstance(raw_value, str):
            return [origin.strip() for origin in raw_value.split(",") if origin.strip()]
        return raw_value

    @property
    def is_llm_configured(self) -> bool:
        """Whether a usable Groq API key is present.

        Returns:
            True when an API key has been provided, enabling live LLM calls.
        """
        return bool(self.groq_api_key.strip())

    @property
    def is_email_configured(self) -> bool:
        """Whether outbound email (SMTP) credentials are present.

        Returns:
            True when both an SMTP username and password are configured,
            enabling the "Email report" action.
        """
        return bool(self.smtp_username.strip() and self.smtp_password.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide, cached settings instance.

    Returns:
        The singleton :class:`Settings` object, constructed on first access.
    """
    return Settings()
