"""Shared base class for the five BankIQ agents.

Provides the common machinery every agent needs — a handle to the Groq client,
namespaced logging, and a typed LLM invocation helper — while leaving each
agent's domain logic to its own ``run`` method. Agents hold no per-request
state; all context arrives through method arguments.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.constants import AGENT_DISPLAY_NAMES
from app.core.logging import get_logger
from app.services.llm_client import GroqLlmClient

TModel = TypeVar("TModel", bound=BaseModel)


class BaseAgent:
    """Shared base for all agents.

    Conceptually abstract: subclasses provide a ``run`` method whose signature
    varies by stage, so it is not declared as a formal abstractmethod here.

    Attributes:
        agent_name: Stable identifier for this agent (see ``constants``).
        llm_client: Shared Groq client used for structured LLM calls.
    """

    #: Subclasses set this to their stable agent identifier.
    agent_name: str = "base"

    def __init__(self, llm_client: GroqLlmClient) -> None:
        """Initialize the agent.

        Args:
            llm_client: The shared Groq LLM client.
        """
        self.llm_client = llm_client
        self._logger = get_logger(self.agent_name)

    @property
    def display_name(self) -> str:
        """Human-friendly label for this agent.

        Returns:
            The display name, falling back to the agent identifier.
        """
        return AGENT_DISPLAY_NAMES.get(self.agent_name, self.agent_name)

    async def _invoke_llm(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
        max_output_tokens: int | None = None,
    ) -> TModel:
        """Call the LLM and return a validated structured result.

        Args:
            system_prompt: System message defining role and output contract.
            user_prompt: User message carrying the task and serialized data.
            response_model: The Pydantic model the response must validate as.
            max_output_tokens: Optional output token budget for this call. Small
                JSON stages pass a tight value so their reserved budget does not
                consume the provider's per-minute token limit. Defaults to the
                client's standard budget.

        Returns:
            A validated instance of ``response_model``.

        Raises:
            LlmError: If the call fails or cannot be parsed (propagated from the
                client for the pipeline to handle as a degraded stage).
        """
        self._logger.debug("[%s] invoking LLM for %s", self.agent_name, response_model.__name__)
        return await self.llm_client.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            agent_name=self.agent_name,
            max_output_tokens=max_output_tokens,
        )
