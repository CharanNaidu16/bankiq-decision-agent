"""Domain-specific exception hierarchy for the Enterprise Decision Analysis Agent backend.

A small, explicit hierarchy lets the pipeline distinguish recoverable agent
failures (which trigger graceful degradation) from configuration/data problems
that should surface clearly. Every custom exception derives from
:class:`BankIqError`.
"""

from __future__ import annotations


class BankIqError(Exception):
    """Base class for all Enterprise Decision Analysis Agent application errors."""


class DatasetNotFoundError(BankIqError):
    """Raised when an expected CSV dataset is missing from the data directory.

    This usually means the synthetic data generator has not been run yet.
    """


class DatasetSchemaError(BankIqError):
    """Raised when a loaded dataset is missing required columns."""


class LlmError(BankIqError):
    """Raised when a call to the Groq LLM fails or cannot be parsed.

    Attributes:
        agent_name: The agent that was running when the error occurred, if known.
    """

    def __init__(self, message: str, *, agent_name: str | None = None) -> None:
        """Initialize the error.

        Args:
            message: Human-readable description of the failure.
            agent_name: The agent that triggered the call, for log correlation.
        """
        super().__init__(message)
        self.agent_name = agent_name


class LlmNotConfiguredError(LlmError):
    """Raised when an LLM call is attempted without a configured API key."""


class AgentExecutionError(BankIqError):
    """Raised when an agent fails to produce a valid result.

    Attributes:
        agent_name: The agent that failed.
        original_error: The underlying exception, if any, for diagnostics.
    """

    def __init__(
        self,
        message: str,
        *,
        agent_name: str,
        original_error: Exception | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Human-readable description of the failure.
            agent_name: The agent that failed.
            original_error: The underlying exception that caused this failure.
        """
        super().__init__(message)
        self.agent_name = agent_name
        self.original_error = original_error
