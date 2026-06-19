"""Report models: the board-ready executive report.

Produced by :class:`app.agents.executive_report_agent.ExecutiveReportAgent`,
which composes the upstream intent / analysis / root-cause / impact results into
a structured report for executive consumption.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendedAction(BaseModel):
    """A single recommended remediation action.

    Attributes:
        title: Short imperative title of the action.
        description: What to do and why, in one or two sentences.
        owner: The role accountable for executing the action
            (e.g. "Zonal HR Head").
        timeline: When it should land, expressed as a 30/60/90-day milestone.
        expected_outcome: The measurable result expected if executed.
        priority: Relative priority ("high", "medium", "low").
    """

    title: str
    description: str
    owner: str
    timeline: str
    expected_outcome: str
    priority: str = "high"


class ReportSection(BaseModel):
    """A titled section of narrative content within the report.

    Attributes:
        heading: Section heading (e.g. "What Happened").
        body: Section body as a markdown-friendly string.
        bullets: Optional bullet points emphasizing key facts.
    """

    heading: str
    body: str = ""
    bullets: list[str] = Field(default_factory=list)


class ExecutiveReport(BaseModel):
    """The structured, board-ready executive report.

    Attributes:
        title: Report title.
        executive_summary: A tight paragraph a CEO can read in 15 seconds.
        what_happened: Section describing the observed KPI movement.
        triggering_event: Section naming the originating event.
        why_it_happened: Section explaining the causal chain.
        financial_impact: Section quantifying exposure in ₹ Cr.
        recommended_actions: Prioritized remediation actions.
        confidence_statement: A short statement of overall analytical confidence.
        degraded_notice: Populated when the report was produced in degraded mode;
            rendered as a banner by the frontend.
    """

    title: str
    executive_summary: str
    what_happened: ReportSection
    triggering_event: ReportSection
    why_it_happened: ReportSection
    financial_impact: ReportSection
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    confidence_statement: str = ""
    degraded_notice: str | None = None
