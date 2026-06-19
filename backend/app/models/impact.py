"""Impact models: financial exposure projected over 30/60/90 days.

Produced by :class:`app.agents.impact_forecast_agent.ImpactForecastAgent`. All
monetary figures are stored in crores of rupees (₹ Cr) for direct executive
consumption.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProductImpact(BaseModel):
    """Disbursement impact attributed to a single product type.

    Attributes:
        product: The product type (e.g. "Personal Loan").
        disbursement_at_risk_cr: Disbursement value at risk, in ₹ Cr.
        commentary: Brief explanation of the product-level impact.
    """

    product: str
    disbursement_at_risk_cr: float = Field(ge=0.0)
    commentary: str = ""


class ImpactProjection(BaseModel):
    """Projected financial exposure for a single forecast horizon.

    Attributes:
        horizon_days: The horizon in days (30, 60, or 90).
        revenue_at_risk_cr: Lost / at-risk revenue over the horizon, in ₹ Cr.
        npa_exposure_cr: Projected non-performing-asset exposure, in ₹ Cr.
        total_exposure_cr: Combined total exposure, in ₹ Cr.
        assumptions: Key assumptions behind this horizon's projection.
    """

    horizon_days: int = Field(gt=0)
    revenue_at_risk_cr: float = Field(ge=0.0)
    npa_exposure_cr: float = Field(ge=0.0)
    total_exposure_cr: float = Field(ge=0.0)
    assumptions: str = ""


class ImpactResult(BaseModel):
    """Aggregate output of the impact-forecast stage.

    Attributes:
        projections: One projection per forecast horizon (30/60/90 days).
        product_impacts: Disbursement impact broken down by product.
        customer_lifetime_value_lost_cr: Estimated CLV lost to churn, in ₹ Cr.
        headline_total_exposure_cr: The single headline exposure figure
            (typically the 30-day total), in ₹ Cr.
        summary: Executive summary of the financial impact.
        degraded: True when produced by graceful degradation.
    """

    projections: list[ImpactProjection] = Field(default_factory=list)
    product_impacts: list[ProductImpact] = Field(default_factory=list)
    customer_lifetime_value_lost_cr: float = Field(default=0.0, ge=0.0)
    headline_total_exposure_cr: float = Field(default=0.0, ge=0.0)
    summary: str = ""
    degraded: bool = False
