"""Analysis models: anomalies and per-dataset findings.

Produced by :class:`app.agents.data_analyst_agent.DataAnalystAgent`. The analyst
computes quarter-over-quarter and cross-zone deltas, flags anomalies beyond the
configured thresholds, and aligns event-log entries to metric movements.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class Anomaly(BaseModel):
    """A single material deviation detected in a metric.

    Attributes:
        dataset: Dataset identifier where the anomaly was found.
        metric: The metric name (e.g. "approval_rate").
        zone: The zone the anomaly pertains to.
        quarter: The quarter the anomaly pertains to.
        product: The product type, when the metric is product-scoped.
        baseline_value: The reference value (prior quarter or peer-zone average).
        observed_value: The anomalous observed value.
        delta_pct: Signed percentage change from baseline to observed.
        direction: "increase" or "decrease".
        severity: Qualitative severity ("low", "medium", "high", "critical").
        description: One-sentence plain-English description of the anomaly.
    """

    dataset: str
    metric: str
    zone: str
    quarter: str
    product: str | None = None
    baseline_value: float | None = None
    observed_value: float | None = None
    delta_pct: float | None = None
    direction: str
    severity: str
    description: str


class DatasetFinding(BaseModel):
    """The analyst's summary of one dataset relevant to the question.

    Attributes:
        dataset: Dataset identifier.
        summary: Narrative summary of what the data shows for the scoped zone(s).
        anomalies: Material anomalies detected within this dataset.
    """

    dataset: str
    summary: str
    anomalies: list[Anomaly] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Aggregate output of the data-analyst stage.

    Attributes:
        findings: Per-dataset findings across all examined datasets.
        flagged_anomalies: The flat, de-duplicated list of all material anomalies.
        timeline_summary: Chronological narrative aligning event-log entries to
            observed metric movements.
        overall_summary: A short executive summary of the analytical picture.
        degraded: True when this result was produced by graceful degradation
            rather than a successful LLM analysis.
    """

    findings: list[DatasetFinding] = Field(default_factory=list)
    flagged_anomalies: list[Anomaly] = Field(default_factory=list)
    timeline_summary: str = ""
    overall_summary: str = ""
    degraded: bool = False

    def to_prompt_json(self, max_anomalies: int = 15) -> str:
        """Serialize a compact view of the analysis for downstream prompts.

        The full result can carry dozens of anomalies (a turnaround zone moves
        almost every metric, in both directions, across all four quarters). Feeding
        that verbatim to later agents bloats their prompts and can exceed the
        provider's per-request token limit. This view keeps the per-dataset
        summaries plus only the most material anomalies (ranked by absolute
        percentage change), which is all the root-cause and report stages need.

        Args:
            max_anomalies: Maximum number of top-ranked anomalies to include.

        Returns:
            A compact (no-indent) JSON string of the trimmed analysis.
        """
        ranked = sorted(
            self.flagged_anomalies,
            key=lambda anomaly: abs(anomaly.delta_pct) if anomaly.delta_pct is not None else 0.0,
            reverse=True,
        )[:max_anomalies]
        payload = {
            "overall_summary": self.overall_summary,
            "timeline_summary": self.timeline_summary,
            "dataset_summaries": [
                {
                    "dataset": finding.dataset,
                    "summary": finding.summary,
                    "anomaly_count": len(finding.anomalies),
                }
                for finding in self.findings
            ],
            "top_anomalies": [anomaly.model_dump() for anomaly in ranked],
            "total_anomaly_count": len(self.flagged_anomalies),
            "degraded": self.degraded,
        }
        return json.dumps(payload, default=str)
