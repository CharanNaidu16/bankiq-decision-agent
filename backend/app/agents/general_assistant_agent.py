"""General Assistant Agent: answer banking/finance questions, decline the rest."""

from __future__ import annotations

from app.agents.base_agent import BaseAgent
from app.constants import AGENT_NAME_GENERAL_ASSISTANT
from app.models.triage import DirectAnswer
from app.prompts.triage_prompts import GENERAL_ASSISTANT_SYSTEM_PROMPT


class GeneralAssistantAgent(BaseAgent):
    """Answers general banking/finance/economics questions in a single LLM call."""

    agent_name = AGENT_NAME_GENERAL_ASSISTANT

    async def run(self, question: str) -> DirectAnswer:
        """Answer a general question, or politely decline if off-topic.

        Args:
            question: The original user question.

        Returns:
            A :class:`DirectAnswer` with a concise answer for banking/finance
            topics, or a fixed decline-and-redirect message otherwise.
        """
        user_prompt = f'User question:\n"""\n{question}\n"""'
        answer = await self._invoke_llm(
            system_prompt=GENERAL_ASSISTANT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=DirectAnswer,
        )
        self._logger.info("[%s] answered: %r", self.agent_name, answer.headline)
        return answer
