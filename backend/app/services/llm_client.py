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

import asyncio
import json
import re
from typing import TypeVar

from openai import APIError, APIStatusError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.constants import (
    LLM_JSON_PARSE_MAX_RETRIES,
    LLM_MAX_OUTPUT_TOKENS,
    LLM_RATE_LIMIT_MAX_RETRIES,
    LLM_RATE_LIMIT_MAX_WAIT_SECONDS,
    LLM_SERVER_ERROR_BASE_DELAY_SECONDS,
    LLM_SERVER_ERROR_MAX_RETRIES,
)
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
                # Disable the SDK's opaque auto-retries; rate limits are handled
                # explicitly below with a capped, advised-delay backoff.
                max_retries=0,
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
        max_output_tokens: int | None = None,
    ) -> TModel:
        """Call the LLM and parse its JSON response into a Pydantic model.

        Args:
            system_prompt: The system message establishing the agent's role and
                output contract.
            user_prompt: The user message carrying the task and serialized data.
            response_model: The Pydantic model the response must validate as.
            agent_name: Calling agent's name, used for logging and error context.
            max_output_tokens: Output token budget for this call. Defaults to
                ``LLM_MAX_OUTPUT_TOKENS``; lightweight stages pass a smaller value
                so their reserved budget does not consume the per-minute token
                limit (the reservation counts against TPM even if unused).

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

        token_budget = max_output_tokens or LLM_MAX_OUTPUT_TOKENS
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None
        for attempt in range(LLM_JSON_PARSE_MAX_RETRIES + 1):
            raw_content = await self._request_with_rate_limit_backoff(
                messages, agent_name, token_budget
            )
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
        self, messages: list[dict[str, str]], agent_name: str, max_tokens: int
    ) -> str:
        """Issue a single JSON-mode chat completion request.

        Args:
            messages: The full message list to send.
            agent_name: Calling agent's name for error context.
            max_tokens: Output token budget reserved for this request.

        Returns:
            The raw text content of the model's reply.

        Raises:
            LlmError: If the underlying API call fails.
        """
        assert self._async_client is not None  # guarded by caller
        # Gemini thinking models burn the output budget on internal reasoning and
        # truncate the JSON unless reasoning is disabled; pass reasoning_effort
        # only when configured so non-reasoning models (Groq llama) are unaffected.
        extra_kwargs: dict[str, object] = {}
        if self._settings.llm_reasoning_effort:
            extra_kwargs["reasoning_effort"] = self._settings.llm_reasoning_effort
        try:
            response = await self._async_client.chat.completions.create(
                model=self._settings.groq_model,
                messages=messages,  # type: ignore[arg-type]
                temperature=self._settings.llm_temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **extra_kwargs,  # type: ignore[arg-type]
            )
        except RateLimitError:
            # Let the backoff wrapper decide whether to wait and retry.
            raise
        except APIStatusError as status_error:
            # Transient server errors (5xx, e.g. Gemini's 503 "overloaded") are
            # retryable; let the backoff wrapper handle them. Other status errors
            # (4xx) are not, so surface them immediately.
            if status_error.status_code >= 500:
                raise
            raise LlmError(
                f"Groq API call failed: {status_error}", agent_name=agent_name
            ) from status_error
        except APIError as api_error:
            raise LlmError(
                f"Groq API call failed: {api_error}", agent_name=agent_name
            ) from api_error

        content = response.choices[0].message.content
        if not content:
            raise LlmError("Groq API returned an empty response.", agent_name=agent_name)
        return content

    async def _request_with_rate_limit_backoff(
        self, messages: list[dict[str, str]], agent_name: str, max_tokens: int
    ) -> str:
        """Issue a completion, waiting out short rate-limit delays and retrying.

        On a 429 the provider advises how long to wait. A per-minute (TPM) limit
        clears in seconds, so we sleep that long and retry; a daily (TPD) limit
        advises minutes, so we fail fast and let the stage degrade rather than
        block the pipeline. Non-rate-limit errors are surfaced unchanged.

        Args:
            messages: The full message list to send.
            agent_name: Calling agent's name for logging and error context.
            max_tokens: Output token budget reserved for this request.

        Returns:
            The raw text content of the model's reply.

        Raises:
            LlmError: If the call fails, or the advised wait is too long to retry.
        """
        server_error_attempts = 0
        for attempt in range(LLM_RATE_LIMIT_MAX_RETRIES + 1):
            try:
                return await self._request_completion(messages, agent_name, max_tokens)
            except RateLimitError as rate_error:
                wait_seconds = self._advised_retry_seconds(rate_error)
                can_retry = (
                    attempt < LLM_RATE_LIMIT_MAX_RETRIES
                    and wait_seconds is not None
                    and wait_seconds <= LLM_RATE_LIMIT_MAX_WAIT_SECONDS
                )
                if not can_retry:
                    raise LlmError(
                        f"Groq API call failed: {rate_error}", agent_name=agent_name
                    ) from rate_error
                _logger.warning(
                    "[%s] rate-limited; waiting %.1fs then retrying (%d/%d)",
                    agent_name,
                    wait_seconds,
                    attempt + 1,
                    LLM_RATE_LIMIT_MAX_RETRIES,
                )
                await asyncio.sleep(wait_seconds + 0.5)
            except APIStatusError as server_error:
                # Transient 5xx (e.g. Gemini free-tier 503 "overloaded"): retry a
                # few times with a short exponential backoff. These don't count
                # against the rate-limit loop, so a busy provider doesn't degrade
                # the stage on the first blip.
                if server_error_attempts >= LLM_SERVER_ERROR_MAX_RETRIES:
                    raise LlmError(
                        f"Groq API call failed: {server_error}", agent_name=agent_name
                    ) from server_error
                delay = LLM_SERVER_ERROR_BASE_DELAY_SECONDS * (2**server_error_attempts)
                server_error_attempts += 1
                _logger.warning(
                    "[%s] server error %s; waiting %.1fs then retrying (%d/%d)",
                    agent_name,
                    server_error.status_code,
                    delay,
                    server_error_attempts,
                    LLM_SERVER_ERROR_MAX_RETRIES,
                )
                await asyncio.sleep(delay)
        # Unreachable: the loop either returns or raises, but satisfies typing.
        raise LlmError("Rate-limit retry loop exhausted.", agent_name=agent_name)

    @staticmethod
    def _advised_retry_seconds(error: RateLimitError) -> float | None:
        """Extract the provider's advised retry delay, in seconds.

        Prefers the ``Retry-After`` header, then falls back to parsing the error
        message (Groq phrases it as e.g. "try again in 11.855s" or "in
        3m52.416s").

        Args:
            error: The rate-limit error raised by the SDK.

        Returns:
            The advised wait in seconds, or ``None`` if it cannot be determined.
        """
        response = getattr(error, "response", None)
        if response is not None:
            header_value = response.headers.get("retry-after")
            if header_value:
                try:
                    return float(header_value)
                except ValueError:
                    pass
        match = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(error))
        if match:
            minutes = int(match.group(1)) if match.group(1) else 0
            return minutes * 60 + float(match.group(2))
        return None

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
