"""Root Cause Agent: assemble the causal chain and name the trigger."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_ROOT_CAUSE, DATASET_EVENT_LOG
from app.models.analysis import AnalysisResult
from app.models.intent import ParsedIntent
from app.models.root_cause import RootCauseResult
from app.prompts.root_cause_prompts import ROOT_CAUSE_SYSTEM_PROMPT
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient


class RootCauseAgent(BaseAgent):
    """Correlates anomalies with the event log to build a causal chain."""

    agent_name = AGENT_NAME_ROOT_CAUSE

    def __init__(
        self, llm_client: GroqLlmClient, dataset_repository: DatasetRepository
    ) -> None:
        """Initialize the agent.

        Args:
            llm_client: The shared Groq LLM client.
            dataset_repository: Repository used to fetch the event log slice.
        """
        super().__init__(llm_client)
        self.dataset_repository = dataset_repository

    async def run(
        self, parsed_intent: ParsedIntent, analysis_result: AnalysisResult
    ) -> RootCauseResult:
        """Build the causal chain explaining the KPI movement.

        The full event log for the focus zone is always re-supplied here so the
        triggering "smoking gun" event is guaranteed to be in context alongside
        the flagged anomalies.

        Args:
            parsed_intent: The investigation scope.
            analysis_result: Anomalies and timeline from the analyst stage.

        Returns:
            The :class:`RootCauseResult` with trigger, chain, and confidence.
        """
        focus_zones = [parsed_intent.focus_zone] if parsed_intent.focus_zone else None
        event_log_markdown = self.dataset_repository.serialize_dataset_slice_to_markdown(
            DATASET_EVENT_LOG, zones=focus_zones
        )
        anomalies_json = analysis_result.model_dump_json(indent=2)
        user_prompt = self._build_user_prompt(
            parsed_intent, anomalies_json, event_log_markdown
        )
        root_cause_result = await self._invoke_llm(
            system_prompt=ROOT_CAUSE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=RootCauseResult,
        )
        trigger = root_cause_result.triggering_event
        self._logger.info(
            "[%s] trigger=%r links=%d overall_confidence=%.2f",
            self.agent_name,
            trigger.event_id if trigger else None,
            len(root_cause_result.causal_chain.links),
            root_cause_result.causal_chain.overall_confidence,
        )
        return root_cause_result

    @staticmethod
    def _build_user_prompt(
        parsed_intent: ParsedIntent,
        anomalies_json: str,
        event_log_markdown: str,
    ) -> str:
        """Assemble the root-cause user prompt.

        Args:
            parsed_intent: The investigation scope.
            anomalies_json: The analyst's result serialized as JSON.
            event_log_markdown: The focus-zone event log as a markdown table.

        Returns:
            The composed user prompt string.
        """
        return (
            "INVESTIGATION SCOPE\n"
            f"- Primary KPI: {parsed_intent.primary_kpi}\n"
            f"- Focus zone: {parsed_intent.focus_zone or 'all zones'}\n"
            f"- Focus quarter: {parsed_intent.focus_quarter or 'unspecified'}\n\n"
            "FLAGGED ANALYSIS (JSON)\n"
            f"{anomalies_json}\n\n"
            "EVENT LOG FOR THE FOCUS ZONE (markdown)\n"
            f"{event_log_markdown}\n"
        )
