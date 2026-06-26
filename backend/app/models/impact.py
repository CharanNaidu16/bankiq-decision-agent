"""Impact models: financial exposure projected over 30/60/90 days.

Produced by :class:`app.agents.impact_forecast_agent.ImpactForecastAgent`. All
monetary figures are stored in crores of rupees (₹ Cr) for direct executive
consumption.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ProductImpact(BaseModel):
    """Disbursement impact attributed to a single product type.

    Attributes:
        product: The product type (e.g. "Personal Loan").
        disbursement_at_risk_cr: Disbursement delta in ₹ Cr. Positive = at risk
            (loss scenario); negative = opportunity captured (gain scenario).
        commentary: Brief explanation of the product-level impact.
    """

    product: str
    disbursement_at_risk_cr: float = 0.0
    commentary: str = ""


class ImpactProjection(BaseModel):
    """Projected financial impact for a single forecast horizon.

    For risk (negative KPI) scenarios all three monetary fields are positive
    (loss/exposure). For opportunity (positive KPI) scenarios the same fields
    carry the magnitude of value captured — still expressed as positive numbers
    because the sign context is carried by ``ImpactResult.scenario_type``.

    Attributes:
        horizon_days: The horizon in days (30, 60, or 90).
        revenue_at_risk_cr: Revenue at risk (risk) or revenue opportunity
            captured (opportunity), in ₹ Cr.
        npa_exposure_cr: NPA exposure increase (risk) or NPA reduction
            (opportunity), in ₹ Cr.
        total_exposure_cr: Combined total for this horizon, in ₹ Cr.
        assumptions: Key assumptions behind this horizon's projection.
    """

    horizon_days: int = Field(gt=0)
    revenue_at_risk_cr: float = 0.0
    npa_exposure_cr: float = 0.0
    total_exposure_cr: float = 0.0
    assumptions: str = ""

    @model_validator(mode="after")
    def _enforce_positive_and_reconcile(self) -> "ImpactProjection":
        """Guarantee positive magnitudes and that the total reconciles.

        The LLM occasionally emits a negative figure (e.g. an NPA *reduction* as
        ``-5``) or a total that does not equal its parts (``14 + -5 = 19``). Sign
        is carried by :attr:`ImpactResult.scenario_type`, not by the numbers, so
        we force every component to a positive magnitude and recompute the total
        as ``revenue + npa`` — making the projection internally consistent no
        matter what the model returned.

        Returns:
            The reconciled projection.
        """
        self.revenue_at_risk_cr = round(abs(self.revenue_at_risk_cr), 2)
        self.npa_exposure_cr = round(abs(self.npa_exposure_cr), 2)
        self.total_exposure_cr = round(self.revenue_at_risk_cr + self.npa_exposure_cr, 2)
        return self


class ImpactResult(BaseModel):
    """Aggregate output of the impact-forecast stage.

    Attributes:
        scenario_type: ``"risk"`` when the KPI moved negatively (loss/exposure
            framing); ``"opportunity"`` when the KPI improved (value-captured
            framing). Drives how the executive report frames the findings.
        projections: One projection per forecast horizon (30/60/90 days).
        product_impacts: Disbursement impact broken down by product.
        customer_lifetime_value_lost_cr: CLV lost to churn (risk) or CLV
            retained/gained (opportunity), in ₹ Cr.
        headline_total_exposure_cr: The single headline figure (30-day total),
            in ₹ Cr.
        summary: Executive summary of the financial impact.
        degraded: True when produced by graceful degradation.
    """

    scenario_type: str = "risk"
    projections: list[ImpactProjection] = Field(default_factory=list)
    product_impacts: list[ProductImpact] = Field(default_factory=list)
    customer_lifetime_value_lost_cr: float = 0.0
    headline_total_exposure_cr: float = 0.0
    summary: str = ""
    degraded: bool = False

    @model_validator(mode="after")
    def _sync_headline_to_thirty_day(self) -> "ImpactResult":
        """Keep the headline figure consistent with the 30-day projection.

        The headline is meant to be the 30-day total; the LLM sometimes reports a
        different number. When a 30-day projection exists, we adopt its
        (already-reconciled) total as the headline so the report's lead figure
        always matches the table. CLV is forced positive for the same
        sign-convention reason as the projection fields.

        Returns:
            The result with a consistent headline figure.
        """
        self.customer_lifetime_value_lost_cr = round(
            abs(self.customer_lifetime_value_lost_cr), 2
        )
        thirty_day = next(
            (p for p in self.projections if p.horizon_days == 30), None
        )
        if thirty_day is not None:
            self.headline_total_exposure_cr = thirty_day.total_exposure_cr
        else:
            self.headline_total_exposure_cr = round(
                abs(self.headline_total_exposure_cr), 2
            )
        return self
