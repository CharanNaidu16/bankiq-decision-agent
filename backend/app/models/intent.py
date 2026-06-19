"""Intent model: the structured interpretation of the user's question.

Produced by :class:`app.agents.intent_agent.IntentAgent` and consumed by every
downstream agent to scope the investigation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    """Structured representation of a natural-language banking question.

    Attributes:
        primary_kpi: The headline metric the user is asking about
            (e.g. "loan approval rate").
        focus_zone: The banking zone in scope, or ``None`` for all zones.
        focus_quarter: The quarter in scope (e.g. "Q3 2025"), or ``None``.
        comparison_quarter: The baseline quarter to compare against, when the
            question implies a change (e.g. the prior quarter).
        focus_product: The product type in scope, if the question names one.
        target_datasets: Dataset identifiers the analyst should read, ranked by
            relevance to the question.
        normalized_question: A cleaned, unambiguous restatement of the question.
        interpretation_notes: Brief notes on how the question was interpreted,
            including any assumptions made about missing details.
    """

    primary_kpi: str
    focus_zone: str | None = None
    focus_quarter: str | None = None
    comparison_quarter: str | None = None
    focus_product: str | None = None
    target_datasets: list[str] = Field(default_factory=list)
    normalized_question: str
    interpretation_notes: str = ""
