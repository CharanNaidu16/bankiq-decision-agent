"""Data Analyst Agent: compute deltas and flag anomalies across datasets."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_DATA_ANALYST
from app.models.analysis import AnalysisResult
from app.models.intent import ParsedIntent
from app.prompts.analysis_prompts import ANALYSIS_SYSTEM_PROMPT
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient


class DataAnalystAgent(BaseAgent):
    """Reads the relevant datasets and flags material anomalies via the LLM."""

    agent_name = AGENT_NAME_DATA_ANALYST

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

    async def run(self, parsed_intent: ParsedIntent) -> AnalysisResult:
        """Analyze the scoped datasets and return flagged anomalies.

        Full data (all zones, all quarters) is supplied so the LLM can compute
        both quarter-over-quarter and cross-zone deltas. The event log is always
        included unfiltered so the triggering event stays in context.

        Args:
            parsed_intent: The structured investigation scope.

        Returns:
            The :class:`AnalysisResult` with per-dataset findings and a flat,
            de-duplicated anomaly list.
        """
        # Scope to the comparison + focus quarters across all zones: enough for
        # both quarter-over-quarter and cross-zone deltas, while keeping the
        # serialized context (and token cost) small. The event log is always
        # included unfiltered by the repository.
        scoped_quarters = [
            quarter
            for quarter in (parsed_intent.comparison_quarter, parsed_intent.focus_quarter)
            if quarter
        ] or None
        serialized_data = self.dataset_repository.serialize_datasets_for_analysis(
            parsed_intent.target_datasets, quarters=scoped_quarters
        )
        user_prompt = self._build_user_prompt(parsed_intent, serialized_data)
        analysis_result = await self._invoke_llm(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=AnalysisResult,
        )
        self._logger.info(
            "[%s] flagged %d anomalies across %d datasets",
            self.agent_name,
            len(analysis_result.flagged_anomalies),
            len(analysis_result.findings),
        )
        return analysis_result

    @staticmethod
    def _build_user_prompt(parsed_intent: ParsedIntent, serialized_data: str) -> str:
        """Assemble the analyst user prompt from scope and serialized data.

        Args:
            parsed_intent: The investigation scope.
            serialized_data: Markdown tables for the target datasets.

        Returns:
            The composed user prompt string.
        """
        return (
            "INVESTIGATION SCOPE\n"
            f"- Primary KPI: {parsed_intent.primary_kpi}\n"
            f"- Focus zone: {parsed_intent.focus_zone or 'all zones'}\n"
            f"- Focus quarter: {parsed_intent.focus_quarter or 'unspecified'}\n"
            f"- Comparison quarter: {parsed_intent.comparison_quarter or 'prior quarter'}\n"
            f"- Focus product: {parsed_intent.focus_product or 'all products'}\n"
            f"- Normalized question: {parsed_intent.normalized_question}\n\n"
            "DATASETS (markdown tables)\n"
            f"{serialized_data}\n"
        )
