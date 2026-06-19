"""Top-level investigation models: request, the typed context bus, and result.

``InvestigationContext`` is the typed bus that flows through the pipeline. Each
agent reads the fields it needs and the pipeline attaches that agent's result
back onto the context for the next stage. Agents themselves remain stateless;
the context is the only thing that accumulates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.analysis import AnalysisResult
from app.models.impact import ImpactResult
from app.models.intent import ParsedIntent
from app.models.report import ExecutiveReport
from app.models.root_cause import RootCauseResult


class InvestigationRequest(BaseModel):
    """Inbound request carrying the user's natural-language question.

    Attributes:
        question: The plain-English banking question to investigate.
    """

    question: str = Field(min_length=3, max_length=2000)


class InvestigationContext(BaseModel):
    """The typed context passed between agents as the pipeline progresses.

    Fields are populated incrementally: the intent agent sets ``parsed_intent``,
    the analyst sets ``analysis_result``, and so on. Downstream agents read
    earlier results from this object.

    Attributes:
        question: The original user question.
        parsed_intent: Output of the intent agent.
        analysis_result: Output of the data-analyst agent.
        root_cause_result: Output of the root-cause agent.
        impact_result: Output of the impact-forecast agent.
    """

    question: str
    parsed_intent: ParsedIntent | None = None
    analysis_result: AnalysisResult | None = None
    root_cause_result: RootCauseResult | None = None
    impact_result: ImpactResult | None = None


class FinalReport(BaseModel):
    """The terminal payload streamed to the client once the pipeline finishes.

    Attributes:
        question: The original user question, echoed back.
        report: The structured executive report.
        parsed_intent: The interpreted intent, included for transparency.
        analysis_result: The analytical findings, included for transparency.
        root_cause_result: The causal chain, included for transparency.
        impact_result: The financial impact, included for transparency.
        degraded: True when any stage fell back to graceful degradation.
        duration_ms: Total wall-clock pipeline duration in milliseconds.
    """

    question: str
    report: ExecutiveReport
    parsed_intent: ParsedIntent | None = None
    analysis_result: AnalysisResult | None = None
    root_cause_result: RootCauseResult | None = None
    impact_result: ImpactResult | None = None
    degraded: bool = False
    duration_ms: float = Field(default=0.0, ge=0.0)
