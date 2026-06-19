"""Intent Agent: parse a natural-language question into a typed scope."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import (
    AGENT_NAME_INTENT,
    ALL_DATASET_NAMES,
    DATASET_EVENT_LOG,
    DATASET_LOAN_PERFORMANCE,
    DATASET_STAFFING,
)
from app.models.intent import ParsedIntent
from app.prompts.intent_prompts import INTENT_SYSTEM_PROMPT


class IntentAgent(BaseAgent):
    """Parses the executive's question and routes it to relevant datasets."""

    agent_name = AGENT_NAME_INTENT

    async def run(self, question: str) -> ParsedIntent:
        """Parse a natural-language banking question into a structured intent.

        Args:
            question: The plain-English question from the user.

        Returns:
            The structured :class:`ParsedIntent`. ``target_datasets`` is
            sanitized to known dataset identifiers and always includes the
            datasets needed for operational root-cause analysis.
        """
        user_prompt = f"Executive question to interpret:\n\"\"\"\n{question}\n\"\"\""
        parsed_intent = await self._invoke_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ParsedIntent,
        )
        parsed_intent.target_datasets = self._sanitize_target_datasets(
            parsed_intent.target_datasets
        )
        self._logger.info(
            "[%s] kpi=%r zone=%r quarter=%r datasets=%s",
            self.agent_name,
            parsed_intent.primary_kpi,
            parsed_intent.focus_zone,
            parsed_intent.focus_quarter,
            parsed_intent.target_datasets,
        )
        return parsed_intent

    @staticmethod
    def _sanitize_target_datasets(requested_datasets: list[str]) -> list[str]:
        """Keep only known datasets and guarantee the essential ones are present.

        Staffing and the event log are always included because operational and
        personnel events are the most common root causes; the loan-performance
        table is included as the canonical KPI source.

        Args:
            requested_datasets: Dataset identifiers proposed by the LLM.

        Returns:
            A de-duplicated, order-preserving list of valid dataset identifiers
            augmented with the mandatory datasets.
        """
        valid_requested = [
            dataset for dataset in requested_datasets if dataset in ALL_DATASET_NAMES
        ]
        mandatory = [DATASET_LOAN_PERFORMANCE, DATASET_STAFFING, DATASET_EVENT_LOG]
        ordered: list[str] = []
        for dataset in [*valid_requested, *mandatory]:
            if dataset not in ordered:
                ordered.append(dataset)
        # Fall back to all datasets if the model returned nothing usable.
        return ordered or list(ALL_DATASET_NAMES)
