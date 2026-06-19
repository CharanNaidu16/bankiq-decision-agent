"""Groq LLM client and structured-output helper.

This module is the single seam between BankIQ and the Groq API. Groq exposes an
OpenAI-compatible endpoint, so we use the official ``openai`` SDK with the
``base_url`` pointed at Groq. Swapping models or providers should only ever
require touching this file plus ``config.py``.

The :meth:`GroqLlmClient.complete_structured` helper requests JSON-mode output,
validates it against a caller-supplied Pydantic model, and performs one bounded
retry on parse failure before surfacing an :class:`LlmError`.
"""

from __future__ import annotations

import json
from typing import TypeVar

from openai import APIError, AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.constants import LLM_JSON_PARSE_MAX_RETRIES, LLM_MAX_OUTPUT_TOKENS
from app.core.exceptions import LlmError, LlmNotConfiguredError
from app.core.logging import get_logger

_logger = get_logger("llm_client")

TModel = TypeVar("TModel", bound=BaseModel)

_JSON_RETRY_REMINDER: str = (
    "Your previous response was not valid JSON that matches the required schema. "
    "Respond again with ONLY a single valid JSON object, no prose, no markdown fences."
)


class GroqLlmClient:
    """Thin async wrapper over the Groq (OpenAI-compatible) chat API."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the client.

        Args:
            settings: Application settings. Defaults to the cached singleton.
        """
        self._settings: Settings = settings or get_settings()
        self._async_client: AsyncOpenAI | None = None
        if self._settings.is_llm_configured:
            self._async_client = AsyncOpenAI(
                api_key=self._settings.groq_api_key,
                base_url=self._settings.groq_base_url,
                timeout=self._settings.llm_request_timeout_seconds,
            )

    @property
    def is_configured(self) -> bool:
        """Whether the client can make live LLM calls.

        Returns:
            True when an API key was provided and the SDK client exists.
        """
        return self._async_client is not None

    async def complete_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
        agent_name: str,
    ) -> TModel:
        """Call the LLM and parse its JSON response into a Pydantic model.

        Args:
            system_prompt: The system message establishing the agent's role and
                output contract.
            user_prompt: The user message carrying the task and serialized data.
            response_model: The Pydantic model the response must validate as.
            agent_name: Calling agent's name, used for logging and error context.

        Returns:
            An instance of ``response_model`` parsed from the model's reply.

        Raises:
            LlmNotConfiguredError: If no API key is configured.
            LlmError: If the API call fails or the response cannot be parsed as
                valid JSON for ``response_model`` after the bounded retry.
        """
        if self._async_client is None:
            raise LlmNotConfiguredError(
                "Groq API key is not configured; cannot make LLM calls.",
                agent_name=agent_name,
            )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(LLM_JSON_PARSE_MAX_RETRIES + 1):
            raw_content = await self._request_completion(messages, agent_name)
            try:
                return self._parse_response(raw_content, response_model)
            except (ValidationError, json.JSONDecodeError) as parse_error:
                last_error = parse_error
                _logger.warning(
                    "[%s] LLM response failed validation (attempt %d/%d): %s",
                    agent_name,
                    attempt + 1,
                    LLM_JSON_PARSE_MAX_RETRIES + 1,
                    parse_error,
                )
                # Feed the bad reply back and ask for clean JSON on retry.
                messages.append({"role": "assistant", "content": raw_content})
                messages.append({"role": "user", "content": _JSON_RETRY_REMINDER})

        raise LlmError(
            f"Could not obtain valid structured output from the LLM: {last_error}",
            agent_name=agent_name,
        )

    async def _request_completion(
        self, messages: list[dict[str, str]], agent_name: str
    ) -> str:
        """Issue a single JSON-mode chat completion request.

        Args:
            messages: The full message list to send.
            agent_name: Calling agent's name for error context.

        Returns:
            The raw text content of the model's reply.

        Raises:
            LlmError: If the underlying API call fails.
        """
        assert self._async_client is not None  # guarded by caller
        try:
            response = await self._async_client.chat.completions.create(
                model=self._settings.groq_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self._settings.llm_temperature,
                max_tokens=LLM_MAX_OUTPUT_TOKENS,
                response_format={"type": "json_object"},
            )
        except APIError as api_error:
            raise LlmError(
                f"Groq API call failed: {api_error}", agent_name=agent_name
            ) from api_error

        content = response.choices[0].message.content
        if not content:
            raise LlmError("Groq API returned an empty response.", agent_name=agent_name)
        return content

    @staticmethod
    def _parse_response(raw_content: str, response_model: type[TModel]) -> TModel:
        """Parse and validate raw model text into the target Pydantic model.

        Tolerates models that wrap JSON in markdown code fences.

        Args:
            raw_content: The raw text returned by the model.
            response_model: The Pydantic model to validate against.

        Returns:
            A validated instance of ``response_model``.

        Raises:
            json.JSONDecodeError: If the content is not valid JSON.
            ValidationError: If the JSON does not satisfy the model schema.
        """
        cleaned = raw_content.strip()
        if cleaned.startswith("```"):
            # Strip a leading ```json / ``` fence and the trailing fence.
            cleaned = cleaned.split("```", 2)[1]
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip().rstrip("`").strip()
        return response_model.model_validate_json(cleaned)
