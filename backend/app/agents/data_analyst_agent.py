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

        When the question names a focus zone, the analysis is scoped to that zone
        across all four quarters: this keeps the investigation on the zone that
        was actually asked about, exposes the full-year trajectory (essential for
        turnaround/trend questions), and bounds the serialized context so a
        verbose, many-anomaly analysis does not overflow the output budget. When
        no zone is named, all zones are supplied for the focus/comparison quarters
        so cross-zone comparisons remain possible. The event log is always
        included (filtered to the same zone) so the triggering event stays in
        context.

        Args:
            parsed_intent: The structured investigation scope.

        Returns:
            The :class:`AnalysisResult` with per-dataset findings and a flat,
            de-duplicated anomaly list.
        """
        if parsed_intent.focus_zone:
            # Single named zone: all quarters, that zone only.
            serialized_data = self.dataset_repository.serialize_datasets_for_analysis(
                parsed_intent.target_datasets, zones=[parsed_intent.focus_zone]
            )
        else:
            # No zone named: all zones, scoped to the comparison + focus quarters
            # so cross-zone deltas are possible without serializing everything.
            scoped_quarters = [
                quarter
                for quarter in (
                    parsed_intent.comparison_quarter,
                    parsed_intent.focus_quarter,
                )
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
            "DATASETS (CSV; one block per dataset)\n"
            f"{serialized_data}\n"
        )
