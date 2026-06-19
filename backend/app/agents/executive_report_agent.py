"""Executive Report Agent: compose the board-ready report."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_EXECUTIVE_REPORT
from app.models.investigation import InvestigationContext
from app.models.report import ExecutiveReport
from app.prompts.report_prompts import REPORT_SYSTEM_PROMPT


class ExecutiveReportAgent(BaseAgent):
    """Synthesizes the full investigation into a structured executive report."""

    agent_name = AGENT_NAME_EXECUTIVE_REPORT

    async def run(self, context: InvestigationContext) -> ExecutiveReport:
        """Compose the executive report from the accumulated context.

        Args:
            context: The investigation context with intent, analysis, root
                cause, and impact results populated.

        Returns:
            The structured :class:`ExecutiveReport`.
        """
        user_prompt = self._build_user_prompt(context)
        executive_report = await self._invoke_llm(
            system_prompt=REPORT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ExecutiveReport,
        )
        self._logger.info(
            "[%s] report composed with %d recommended actions",
            self.agent_name,
            len(executive_report.recommended_actions),
        )
        return executive_report

    @staticmethod
    def _build_user_prompt(context: InvestigationContext) -> str:
        """Assemble the report user prompt from the full investigation context.

        Args:
            context: The populated investigation context.

        Returns:
            The composed user prompt string.
        """
        intent_json = (
            context.parsed_intent.model_dump_json(indent=2)
            if context.parsed_intent
            else "{}"
        )
        analysis_json = (
            context.analysis_result.model_dump_json(indent=2)
            if context.analysis_result
            else "{}"
        )
        root_cause_json = (
            context.root_cause_result.model_dump_json(indent=2)
            if context.root_cause_result
            else "{}"
        )
        impact_json = (
            context.impact_result.model_dump_json(indent=2)
            if context.impact_result
            else "{}"
        )
        return (
            f"ORIGINAL QUESTION\n{context.question}\n\n"
            f"PARSED INTENT (JSON)\n{intent_json}\n\n"
            f"ANALYSIS (JSON)\n{analysis_json}\n\n"
            f"ROOT CAUSE (JSON)\n{root_cause_json}\n\n"
            f"FINANCIAL IMPACT (JSON)\n{impact_json}\n"
        )
