"""Simple Query Agent: answer a factual data lookup without a full investigation."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_SIMPLE_QUERY
from app.models.intent import ParsedIntent
from app.models.triage import DirectAnswer
from app.prompts.triage_prompts import SIMPLE_QUERY_SYSTEM_PROMPT
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient


class SimpleQueryAgent(BaseAgent):
    """Answers a scoped factual question directly from the relevant data slice."""

    agent_name = AGENT_NAME_SIMPLE_QUERY

    def __init__(
        self, llm_client: GroqLlmClient, dataset_repository: DatasetRepository
    ) -> None:
        """Initialize the agent.

        Args:
            llm_client: The shared Groq LLM client.
            dataset_repository: Repository used to load and serialize datasets.
        """
        super().__init__(llm_client)
        self.dataset_repository = dataset_repository

    async def run(self, question: str, parsed_intent: ParsedIntent) -> DirectAnswer:
        """Answer a factual question from the scoped datasets.

        The scope from the intent agent narrows the data slice; the LLM then
        reads the markdown tables and computes the answer directly, with no
        root-cause, impact, or report stages.

        Args:
            question: The original user question.
            parsed_intent: The structured scope (zones, quarters, datasets).

        Returns:
            A :class:`DirectAnswer` with the concise, data-grounded response.
        """
        focus_zones = [parsed_intent.focus_zone] if parsed_intent.focus_zone else None
        scoped_quarters = [
            quarter
            for quarter in (parsed_intent.comparison_quarter, parsed_intent.focus_quarter)
            if quarter
        ] or None
        serialized_data = self.dataset_repository.serialize_datasets_for_analysis(
            parsed_intent.target_datasets, zones=focus_zones, quarters=scoped_quarters
        )
        user_prompt = (
            f"QUESTION\n{question}\n\n"
            "SCOPE\n"
            f"- Focus zone: {parsed_intent.focus_zone or 'all zones'}\n"
            f"- Focus quarter: {parsed_intent.focus_quarter or 'unspecified'}\n"
            f"- Focus product: {parsed_intent.focus_product or 'all products'}\n\n"
            "DATASETS (markdown tables)\n"
            f"{serialized_data}\n"
        )
        answer = await self._invoke_llm(
            system_prompt=SIMPLE_QUERY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=DirectAnswer,
        )
        self._logger.info("[%s] answered: %r", self.agent_name, answer.headline)
        return answer
