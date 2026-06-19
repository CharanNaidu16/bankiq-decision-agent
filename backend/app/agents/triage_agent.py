"""Triage Agent: classify a question and enforce read-only guardrails."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_TRIAGE
from app.models.triage import TriageDecision
from app.prompts.triage_prompts import TRIAGE_SYSTEM_PROMPT


class TriageAgent(BaseAgent):
    """Routes each question to the right path and rejects unsafe requests."""

    agent_name = AGENT_NAME_TRIAGE

    async def run(self, question: str) -> TriageDecision:
        """Classify a question into one of the four handling categories.

        Args:
            question: The plain-English message from the user.

        Returns:
            The :class:`TriageDecision` with the routing category, confidence,
            and (for rejections) which guardrail tripped.
        """
        user_prompt = f'User message to classify:\n"""\n{question}\n"""'
        decision = await self._invoke_llm(
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TriageDecision,
        )
        self._logger.info(
            "[%s] category=%s confidence=%.2f reason=%r",
            self.agent_name,
            decision.category,
            decision.confidence,
            decision.refusal_reason or decision.reasoning,
        )
        return decision
