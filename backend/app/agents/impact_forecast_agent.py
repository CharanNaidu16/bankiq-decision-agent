"""Impact Forecast Agent: quantify financial exposure over 30/60/90 days."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base_agent import BaseAgent
from app.constants import (
    AGENT_NAME_IMPACT_FORECAST,
    DATASET_LOAN_PERFORMANCE,
    DATASET_PRODUCT_PERFORMANCE,
    DATASET_RISK_METRICS,
)
from app.models.impact import ImpactResult
from app.models.intent import ParsedIntent
from app.models.root_cause import RootCauseResult
from app.prompts.impact_prompts import IMPACT_SYSTEM_PROMPT
from app.services.dataset_repository import DatasetRepository
from app.services.llm_client import GroqLlmClient

# Datasets carrying the figures needed to quantify financial exposure.
_FINANCIAL_DATASETS: tuple[str, ...] = (
    DATASET_PRODUCT_PERFORMANCE,
    DATASET_LOAN_PERFORMANCE,
    DATASET_RISK_METRICS,
)

# One crore = 10,000,000 rupees. Raw amounts in the datasets are in rupees.
_RUPEES_PER_CRORE: float = 10_000_000.0
# Horizon-to-fraction map: the observed quarter-over-quarter change is treated as
# the quarterly (~90-day) run-rate, so 30/60/90-day exposure is 1/3, 2/3, and the
# full quarterly delta respectively — grounded and monotonic, never a ×3 blow-up.
_HORIZON_FRACTIONS: dict[int, float] = {30: 1.0 / 3.0, 60: 2.0 / 3.0, 90: 1.0}


@dataclass(frozen=True)
class _GroundedAnchors:
    """Data-derived monetary anchors for the projection figures (in ₹ Cr).

    Attributes:
        revenue_per_quarter_cr: Magnitude of the disbursement change per quarter.
        npa_per_quarter_cr: Magnitude of the provisioning change per quarter.
    """

    revenue_per_quarter_cr: float
    npa_per_quarter_cr: float

    def for_horizon(self, horizon_days: int) -> tuple[float, float]:
        """Return grounded (revenue, npa) in ₹ Cr for a 30/60/90-day horizon.

        Args:
            horizon_days: The projection horizon (30, 60, or 90).

        Returns:
            A ``(revenue_at_risk_cr, npa_exposure_cr)`` tuple, rounded to 2 dp.
        """
        fraction = _HORIZON_FRACTIONS.get(horizon_days, 1.0)
        return (
            round(self.revenue_per_quarter_cr * fraction, 2),
            round(self.npa_per_quarter_cr * fraction, 2),
        )


class ImpactForecastAgent(BaseAgent):
    """Projects revenue at risk, NPA exposure, and CLV lost from the root cause."""

    agent_name = AGENT_NAME_IMPACT_FORECAST

    def __init__(
        self, llm_client: GroqLlmClient, dataset_repository: DatasetRepository
    ) -> None:
        """Initialize the agent.

        Args:
            llm_client: The shared Groq LLM client.
            dataset_repository: Repository used to fetch the financial slices.
        """
        super().__init__(llm_client)
        self.dataset_repository = dataset_repository

    async def run(
        self, parsed_intent: ParsedIntent, root_cause_result: RootCauseResult
    ) -> ImpactResult:
        """Quantify financial exposure if the root cause is left unaddressed.

        Args:
            parsed_intent: The investigation scope.
            root_cause_result: The identified root cause and causal chain.

        Returns:
            The :class:`ImpactResult` with 30/60/90-day projections in ₹ Cr.
        """
        focus_zones = [parsed_intent.focus_zone] if parsed_intent.focus_zone else None
        scoped_quarters = [
            quarter
            for quarter in (parsed_intent.comparison_quarter, parsed_intent.focus_quarter)
            if quarter
        ] or None
        financial_csv = self.dataset_repository.serialize_datasets_for_analysis(
            list(_FINANCIAL_DATASETS), zones=focus_zones, quarters=scoped_quarters
        )
        # Compute the money from the data rather than trusting the LLM's big-number
        # arithmetic (it reliably mis-converts rupees→crore by an order of magnitude).
        anchors = self._compute_grounded_anchors(parsed_intent)
        root_cause_json = root_cause_result.model_dump_json(indent=2)
        user_prompt = self._build_user_prompt(
            parsed_intent, root_cause_json, financial_csv, anchors
        )
        impact_result = await self._invoke_llm(
            system_prompt=IMPACT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=ImpactResult,
        )
        if anchors is not None:
            self._apply_grounded_anchors(impact_result, anchors)
        self._logger.info(
            "[%s] headline_exposure=₹%.2f Cr projections=%d grounded=%s",
            self.agent_name,
            impact_result.headline_total_exposure_cr,
            len(impact_result.projections),
            anchors is not None,
        )
        return impact_result

    def _compute_grounded_anchors(
        self, parsed_intent: ParsedIntent
    ) -> _GroundedAnchors | None:
        """Derive the revenue/NPA anchors directly from the datasets.

        Uses the focus zone's ``disbursement_amt`` (revenue) and
        ``provisioning_amt`` (NPA) change between the comparison and focus
        quarters, converted to ₹ Cr and normalized to a per-quarter run-rate.
        Returns ``None`` when the scope is not a single zone/quarter pair, so the
        LLM's own (prompt-grounded) figures are used as a fallback.

        Args:
            parsed_intent: The investigation scope.

        Returns:
            The :class:`_GroundedAnchors`, or ``None`` if the data is not
            available to compute them.
        """
        zone = parsed_intent.focus_zone
        comparison_quarter = parsed_intent.comparison_quarter
        focus_quarter = parsed_intent.focus_quarter
        if not (zone and comparison_quarter and focus_quarter):
            return None

        disbursement_delta = self._amount_delta(
            DATASET_LOAN_PERFORMANCE, "disbursement_amt", zone,
            comparison_quarter, focus_quarter,
        )
        provisioning_delta = self._amount_delta(
            DATASET_RISK_METRICS, "provisioning_amt", zone,
            comparison_quarter, focus_quarter,
        )
        if disbursement_delta is None or provisioning_delta is None:
            return None

        quarters_apart = self._quarters_between(comparison_quarter, focus_quarter)
        return _GroundedAnchors(
            revenue_per_quarter_cr=disbursement_delta / _RUPEES_PER_CRORE / quarters_apart,
            npa_per_quarter_cr=provisioning_delta / _RUPEES_PER_CRORE / quarters_apart,
        )

    def _amount_delta(
        self,
        dataset_name: str,
        column: str,
        zone: str,
        comparison_quarter: str,
        focus_quarter: str,
    ) -> float | None:
        """Return the absolute change in a rupee column between two quarters.

        Args:
            dataset_name: Dataset to read.
            column: The rupee-valued column (e.g. ``disbursement_amt``).
            zone: Focus zone.
            comparison_quarter: Baseline quarter.
            focus_quarter: Affected/improved quarter.

        Returns:
            The absolute delta in rupees, or ``None`` if either value is missing.
        """
        baseline = self._amount(dataset_name, column, zone, comparison_quarter)
        latest = self._amount(dataset_name, column, zone, focus_quarter)
        if baseline is None or latest is None:
            return None
        return abs(latest - baseline)

    def _amount(
        self, dataset_name: str, column: str, zone: str, quarter: str
    ) -> float | None:
        """Read a single rupee value for a zone/quarter, or ``None`` if absent.

        Args:
            dataset_name: Dataset to read.
            column: The column to read.
            zone: Zone to filter to.
            quarter: Quarter to filter to.

        Returns:
            The (summed) column value in rupees, or ``None`` if the slice is
            empty or the column is missing.
        """
        sliced = self.dataset_repository.filter_dataset_slice(
            dataset_name, zones=[zone], quarters=[quarter]
        )
        if sliced.empty or column not in sliced.columns:
            return None
        return float(sliced[column].sum())

    @staticmethod
    def _quarters_between(comparison_quarter: str, focus_quarter: str) -> int:
        """Return the number of quarters between two "Q# YYYY" labels (min 1).

        Args:
            comparison_quarter: e.g. ``"Q1 2025"``.
            focus_quarter: e.g. ``"Q4 2025"``.

        Returns:
            The absolute quarter distance, floored at 1 to avoid divide-by-zero.
        """
        def index(label: str) -> int | None:
            parts = label.replace("Q", "").split()
            if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                return None
            return int(parts[1]) * 4 + int(parts[0])

        start, end = index(comparison_quarter), index(focus_quarter)
        if start is None or end is None:
            return 1
        return max(1, abs(end - start))

    @staticmethod
    def _apply_grounded_anchors(
        impact_result: ImpactResult, anchors: _GroundedAnchors
    ) -> None:
        """Overwrite the projection money with the data-derived anchors.

        The LLM's scenario direction, narrative, and product commentary are kept;
        only the revenue/NPA/total figures (which it mis-converts) are replaced,
        and the headline is re-synced to the 30-day total.

        Args:
            impact_result: The LLM result to correct in place.
            anchors: The data-derived per-quarter anchors.
        """
        for projection in impact_result.projections:
            revenue, npa = anchors.for_horizon(projection.horizon_days)
            projection.revenue_at_risk_cr = revenue
            projection.npa_exposure_cr = npa
            projection.total_exposure_cr = round(revenue + npa, 2)
        thirty_day = next(
            (p for p in impact_result.projections if p.horizon_days == 30), None
        )
        if thirty_day is not None:
            impact_result.headline_total_exposure_cr = thirty_day.total_exposure_cr

    @staticmethod
    def _build_user_prompt(
        parsed_intent: ParsedIntent,
        root_cause_json: str,
        financial_csv: str,
        anchors: _GroundedAnchors | None,
    ) -> str:
        """Assemble the impact-forecast user prompt.

        Args:
            parsed_intent: The investigation scope.
            root_cause_json: The root-cause result serialized as JSON.
            financial_csv: Financial datasets as CSV blocks.
            anchors: Pre-computed, data-grounded projection figures to use
                verbatim, or ``None`` when they could not be derived.

        Returns:
            The composed user prompt string.
        """
        grounded_block = ""
        if anchors is not None:
            r30, n30 = anchors.for_horizon(30)
            r60, n60 = anchors.for_horizon(60)
            r90, n90 = anchors.for_horizon(90)
            grounded_block = (
                "GROUNDED PROJECTION FIGURES (₹ Cr — use these EXACT values; do not "
                "recompute or scale them):\n"
                f"- 30 days: revenue={r30}, npa={n30}, total={round(r30 + n30, 2)}\n"
                f"- 60 days: revenue={r60}, npa={n60}, total={round(r60 + n60, 2)}\n"
                f"- 90 days: revenue={r90}, npa={n90}, total={round(r90 + n90, 2)}\n"
                "Write the summary and assumptions consistent with these figures. "
                "Set headline_total_exposure_cr to the 30-day total above.\n\n"
            )
        return (
            "INVESTIGATION SCOPE\n"
            f"- Primary KPI: {parsed_intent.primary_kpi}\n"
            f"- Focus zone: {parsed_intent.focus_zone or 'all zones'}\n"
            f"- Focus quarter: {parsed_intent.focus_quarter or 'unspecified'}\n"
            f"- Comparison quarter: {parsed_intent.comparison_quarter or 'prior quarter'}\n\n"
            f"{grounded_block}"
            "ROOT CAUSE (JSON)\n"
            f"{root_cause_json}\n\n"
            "FINANCIAL DATASETS (CSV)\n"
            f"{financial_csv}\n"
        )
