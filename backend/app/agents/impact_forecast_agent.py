"""Impact Forecast Agent: quantify financial exposure over 30/60/90 days."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import (
    AGENT_NAME_IMPACT_FORECAST,
    DATASET_LOAN_PERFORMANCE,
    DATASET_PRODUCT_PERFORMANCE,
    DATASET_RISK_METRICS,
)
from app.models.impact import ImpactResult
from app.models.intent import ParsedIntent
from app.models.root_cause import RootCauseResult
from app.prompts.impact_prompts import IMPACT_SYSTEM_PROMPT
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient

# Datasets carrying the figures needed to quantify financial exposure.
_FINANCIAL_DATASETS: tuple[str, ...] = (
    DATASET_PRODUCT_PERFORMANCE,
    DATASET_LOAN_PERFORMANCE,
    DATASET_RISK_METRICS,
)


class ImpactForecastAgent(BaseAgent):
    """Projects revenue at risk, NPA exposure, and CLV lost from the root cause."""

    agent_name = AGENT_NAME_IMPACT_FORECAST

    def __init__(
        self, llm_client: GroqLlmClient, dataset_repository: DatasetRepository
    ) -> None:
        """Initialize the agent.

        Args:
            llm_client: The shared Groq LLM client.
            dataset_repository: Repository used to fetch the financial slices.
        """
        super().__init__(llm_client)
        self.dataset_repository = dataset_repository

    async def run(
        self, parsed_intent: ParsedIntent, root_cause_result: RootCauseResult
    ) -> ImpactResult:
        """Quantify financial exposure if the root cause is left unaddressed.

        Args:
            parsed_intent: The investigation scope.
            root_cause_result: The identified root cause and causal chain.

        Returns:
            The :class:`ImpactResult` with 30/60/90-day projections in ₹ Cr.
        """
        focus_zones = [parsed_intent.focus_zone] if parsed_intent.focus_zone else None
        scoped_quarters = [
            quarter
            for quarter in (parsed_intent.comparison_quarter, parsed_intent.focus_quarter)
            if quarter
        ] or None
        financial_markdown = self.dataset_repository.serialize_datasets_for_analysis(
            list(_FINANCIAL_DATASETS), zones=focus_zones, quarters=scoped_quarters
        )
        root_cause_json = root_cause_result.model_dump_json(indent=2)
        user_prompt = self._build_user_prompt(
            parsed_intent, root_cause_json, financial_markdown
        )
        impact_result = await self._invoke_llm(
            system_prompt=IMPACT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ImpactResult,
        )
        self._logger.info(
            "[%s] headline_exposure=₹%.2f Cr projections=%d",
            self.agent_name,
            impact_result.headline_total_exposure_cr,
            len(impact_result.projections),
        )
        return impact_result

    @staticmethod
    def _build_user_prompt(
        parsed_intent: ParsedIntent,
        root_cause_json: str,
        financial_markdown: str,
    ) -> str:
        """Assemble the impact-forecast user prompt.

        Args:
            parsed_intent: The investigation scope.
            root_cause_json: The root-cause result serialized as JSON.
            financial_markdown: Financial datasets as markdown tables.

        Returns:
            The composed user prompt string.
        """
        return (
            "INVESTIGATION SCOPE\n"
            f"- Primary KPI: {parsed_intent.primary_kpi}\n"
            f"- Focus zone: {parsed_intent.focus_zone or 'all zones'}\n"
            f"- Focus quarter: {parsed_intent.focus_quarter or 'unspecified'}\n"
            f"- Comparison quarter: {parsed_intent.comparison_quarter or 'prior quarter'}\n\n"
            "ROOT CAUSE (JSON)\n"
            f"{root_cause_json}\n\n"
            "FINANCIAL DATASETS (markdown)\n"
            f"{financial_markdown}\n"
        )
