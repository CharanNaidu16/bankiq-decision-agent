"""Root-cause models: the causal chain and the identified triggering event.

Produced by :class:`app.agents.root_cause_agent.RootCauseAgent`, which
cross-references staffing, event-log, and product anomalies to assemble an
ordered causal chain with per-link confidence scores.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriggeringEvent(BaseModel):
    """The originating event identified as the root cause ("smoking gun").

    Attributes:
        event_id: Identifier of the event-log row, when available.
        date: ISO date string of the event.
        zone: Zone where the event occurred.
        event_type: Category of the event (e.g. "resignation").
        description: Human-readable description of the event.
        severity: Event severity ("Low" / "Medium" / "High" / "Critical").
        affected_product: Product most directly affected by the event, if any.
        rationale: Why this event is judged to be the root trigger.
    """

    event_id: str | None = None
    date: str | None = None
    zone: str | None = None
    event_type: str | None = None
    description: str
    severity: str | None = None
    affected_product: str | None = None
    rationale: str


class CausalLink(BaseModel):
    """One directed link in the causal chain (cause -> effect).

    Attributes:
        sequence: One-based position of this link in the chain.
        cause: The causing condition (the prior state or event).
        effect: The resulting condition this cause produced.
        evidence: Concrete data points / anomalies supporting the link.
        confidence: Confidence score in [0, 1] that this link holds.
        supporting_datasets: Datasets whose evidence backs this link.
    """

    sequence: int = Field(ge=1)
    cause: str
    effect: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_datasets: list[str] = Field(default_factory=list)


class CausalChain(BaseModel):
    """The ordered set of causal links from trigger to observed KPI impact.

    Attributes:
        links: Causal links in chronological/causal order.
        narrative: A one-paragraph plain-English statement of the full chain.
        overall_confidence: Aggregate confidence in the chain as a whole [0, 1].
    """

    links: list[CausalLink] = Field(default_factory=list)
    narrative: str = ""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class RootCauseResult(BaseModel):
    """Aggregate output of the root-cause stage.

    Attributes:
        triggering_event: The identified originating event.
        causal_chain: The full causal chain explaining the KPI movement.
        primary_root_cause: One-sentence statement of the dominant root cause.
        degraded: True when produced by graceful degradation.
    """

    triggering_event: TriggeringEvent | None = None
    causal_chain: CausalChain = Field(default_factory=CausalChain)
    primary_root_cause: str = ""
    degraded: bool = False
