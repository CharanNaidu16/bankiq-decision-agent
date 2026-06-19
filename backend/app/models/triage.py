"""Triage models: question classification and lightweight direct answers.

The triage step runs before the investigation pipeline and decides how a
question should be handled. ``TriageDecision`` is the classifier's output;
``QuestionCategory`` is the routing key the pipeline branches on. ``DirectAnswer``
is the small structured payload returned by the lightweight (simple-query and
general-assistant) paths before being mapped into a minimal executive report.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class QuestionCategory(StrEnum):
    """How an incoming question should be routed by the pipeline."""

    #: A KPI anomaly worth the full five-agent investigation.
    INVESTIGATION = "investigation"
    #: A factual lookup answerable from a scoped data slice.
    SIMPLE_QUERY = "simple_query"
    #: A general banking/finance question answerable without the datasets.
    OUT_OF_SCOPE = "out_of_scope"
    #: A guardrail violation (write/destructive/jailbreak) to be refused.
    REJECTED = "rejected"


class TriageDecision(BaseModel):
    """The triage agent's classification of a single user message.

    Attributes:
        category: The routing decision the pipeline branches on.
        confidence: The model's confidence in the classification (0-1).
        reasoning: One-line rationale, surfaced in logs for transparency.
        refusal_reason: Which guardrail tripped; populated only for
            ``REJECTED``. The user-facing refusal text is a fixed server
            constant, never this free-text field.
        degraded: True when the triage LLM call failed and a safe default
            category was substituted.
    """

    category: QuestionCategory
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str = ""
    refusal_reason: str | None = None
    degraded: bool = False


class DirectAnswer(BaseModel):
    """A concise answer produced by a lightweight (non-investigation) path.

    Attributes:
        answer: The user-facing answer text.
        headline: A short title summarizing the answer for the report header.
        degraded: True when the underlying LLM call failed and a fallback
            answer was substituted.
    """

    answer: str
    headline: str = ""
    degraded: bool = False
