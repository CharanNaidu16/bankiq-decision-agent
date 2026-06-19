"""Standalone generator for BankIQ's seven synthetic banking datasets.

Run this once before starting the backend:

    cd backend
    python scripts/generate_synthetic_data.py

It writes seven internally-consistent CSV files into ``backend/data/`` describing
five zones (North/South/East/West/Central) across four quarters of 2025.

A single dominant story is planted in the **South zone, Q3 2025**, derived link
by link so the seven tables reconcile:

    Aug 14 2025: 3 senior underwriters resign (Critical event)
      -> South headcount -22%, open positions spike, training collapses 89% -> 31%
      -> Personal-Loan processing time triples 3 -> 9 days
      -> Personal-Loan approval -31%, overall South approval -18%
      -> NPS 72 -> 41, complaints triple, churn spikes
      -> branch wait times +40%
      -> NPA rate rises, compliance flags increase
      Financial exposure: ₹4.2 Cr lost Personal-Loan disbursement
                        + ₹1.8 Cr NPA provisioning  =  ₹6.0 Cr (30-day, unaddressed)

This script imports nothing from the ``app`` package so it can run on its own.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

# Force UTF-8 stdout so the rupee glyph (₹) prints on legacy Windows consoles.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        with contextlib.suppress(ValueError, OSError):
            _reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Configuration (kept local so the script is self-contained).
# ---------------------------------------------------------------------------
RANDOM_SEED: Final[int] = 42
OUTPUT_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data"

ZONES: Final[tuple[str, ...]] = ("North", "South", "East", "West", "Central")
QUARTERS: Final[tuple[str, ...]] = ("Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025")
PRODUCTS: Final[tuple[str, ...]] = (
    "Home Loan",
    "Personal Loan",
    "Business Loan",
    "Auto Loan",
)

CRORE: Final[int] = 10_000_000  # rupees in one crore

# The zone and quarter that carry the planted anomaly.
STORY_ZONE: Final[str] = "South"
STORY_QUARTER: Final[str] = "Q3 2025"
STORY_RECOVERY_QUARTER: Final[str] = "Q4 2025"
STORY_PRODUCT: Final[str] = "Personal Loan"

console = Console(legacy_windows=False)
_rng = np.random.default_rng(RANDOM_SEED)


def _jitter(base: float, spread_fraction: float) -> float:
    """Apply small, seeded multiplicative noise to a baseline value.

    Used only for non-story zones/quarters so normal data looks natural while
    the planted South-Q3 figures stay exact.

    Args:
        base: The baseline value to perturb.
        spread_fraction: Maximum fractional deviation (e.g. 0.03 for +/-3%).

    Returns:
        The jittered value.
    """
    return float(base * (1.0 + _rng.uniform(-spread_fraction, spread_fraction)))


# ---------------------------------------------------------------------------
# Per-zone / per-product baseline profiles.
# ---------------------------------------------------------------------------
_ZONE_APPROVAL_MULTIPLIER: Final[dict[str, float]] = {
    "North": 1.03,
    "South": 1.00,
    "East": 0.98,
    "West": 1.01,
    "Central": 0.99,
}
_ZONE_SIZE_MULTIPLIER: Final[dict[str, float]] = {
    "North": 1.10,
    "South": 1.00,
    "East": 0.85,
    "West": 1.05,
    "Central": 0.90,
}
_QUARTER_GROWTH: Final[dict[str, float]] = {
    "Q1 2025": 1.00,
    "Q2 2025": 1.02,
    "Q3 2025": 1.03,
    "Q4 2025": 1.05,
}

_PRODUCT_BASE_APPROVAL: Final[dict[str, float]] = {
    "Home Loan": 75.0,
    "Personal Loan": 70.0,
    "Business Loan": 68.0,
    "Auto Loan": 74.0,
}
_PRODUCT_BASE_APPLICATIONS: Final[dict[str, int]] = {
    "Home Loan": 400,
    "Personal Loan": 600,
    "Business Loan": 300,
    "Auto Loan": 360,
}
_PRODUCT_TICKET_SIZE: Final[dict[str, int]] = {
    "Home Loan": 2_500_000,
    "Personal Loan": 300_000,
    "Business Loan": 1_500_000,
    "Auto Loan": 800_000,
}
_PRODUCT_BASE_DEFAULT_RATE: Final[dict[str, float]] = {
    "Home Loan": 1.8,
    "Personal Loan": 3.2,
    "Business Loan": 3.8,
    "Auto Loan": 2.6,
}

# South Q3 story multipliers, applied to the South Q2 baseline.
_STORY_APPROVAL_MULTIPLIER: Final[dict[str, float]] = {
    "Personal Loan": 0.69,  # -31% (the smoking-gun product)
    "Home Loan": 0.88,  # -12% spillover (same underwriters)
    "Business Loan": 0.88,
    "Auto Loan": 0.88,
}


def _build_product_performance() -> pd.DataFrame:
    """Generate the product_performance table (the financial backbone).

    Personal-Loan applications and approval rates are tuned so that the South
    Q3 lost disbursement equals ~₹4.2 Cr versus Q2.

    Returns:
        A DataFrame with one row per (zone, quarter, product_type).
    """
    rows: list[dict[str, object]] = []
    # South Personal-Loan application counts chosen so the Q2->Q3 disbursement
    # gap lands on ₹4.2 Cr (420 approved -> 280 approved at ₹3L ticket).
    south_personal_applications = {
        "Q1 2025": 590,
        "Q2 2025": 600,
        "Q3 2025": 580,
        "Q4 2025": 585,
    }

    for zone in ZONES:
        for quarter in QUARTERS:
            is_story = zone == STORY_ZONE and quarter == STORY_QUARTER
            is_recovery = zone == STORY_ZONE and quarter == STORY_RECOVERY_QUARTER
            for product in PRODUCTS:
                base_approval = (
                    _PRODUCT_BASE_APPROVAL[product]
                    * _ZONE_APPROVAL_MULTIPLIER[zone]
                )
                base_applications = (
                    _PRODUCT_BASE_APPLICATIONS[product]
                    * _ZONE_SIZE_MULTIPLIER[zone]
                    * _QUARTER_GROWTH[quarter]
                )
                base_default = _PRODUCT_BASE_DEFAULT_RATE[product]
                ticket = _PRODUCT_TICKET_SIZE[product]

                if is_story:
                    approval_rate = base_approval * _STORY_APPROVAL_MULTIPLIER[product]
                    default_rate = base_default + (2.0 if product == STORY_PRODUCT else 1.0)
                    if product == STORY_PRODUCT:
                        applications = south_personal_applications[quarter]
                    else:
                        applications = round(base_applications * 0.95)
                elif is_recovery:
                    # Partial recovery in Q4.
                    recovery_factor = 0.80 if product == STORY_PRODUCT else 0.94
                    approval_rate = base_approval * recovery_factor
                    default_rate = base_default + 0.6
                    applications = (
                        south_personal_applications[quarter]
                        if product == STORY_PRODUCT
                        else round(base_applications)
                    )
                elif zone == STORY_ZONE:
                    approval_rate = base_approval
                    default_rate = base_default
                    applications = (
                        south_personal_applications[quarter]
                        if product == STORY_PRODUCT
                        else round(base_applications)
                    )
                else:
                    approval_rate = _jitter(base_approval, 0.02)
                    default_rate = _jitter(base_default, 0.10)
                    applications = round(_jitter(base_applications, 0.05))

                approved_count = round(applications * approval_rate / 100.0)
                disbursement_amt = approved_count * ticket

                rows.append(
                    {
                        "zone": zone,
                        "quarter": quarter,
                        "product_type": product,
                        "approval_rate": round(approval_rate, 1),
                        "disbursement_amt": int(disbursement_amt),
                        "avg_ticket_size": int(ticket),
                        "default_rate": round(default_rate, 2),
                        "application_count": int(applications),
                    }
                )
    return pd.DataFrame(rows)


def _build_loan_performance(product_frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate product_performance up to the zone-level loan_performance table.

    Zone approval rate is the application-weighted mean across products and
    disbursement is the product sum, guaranteeing the two tables reconcile.

    Args:
        product_frame: The generated product_performance DataFrame.

    Returns:
        A DataFrame with one row per (zone, quarter).
    """
    rows: list[dict[str, object]] = []
    for zone in ZONES:
        for quarter in QUARTERS:
            subset = product_frame[
                (product_frame["zone"] == zone) & (product_frame["quarter"] == quarter)
            ]
            total_applications = int(subset["application_count"].sum())
            weighted_approval = float(
                (subset["approval_rate"] * subset["application_count"]).sum()
                / total_applications
            )
            weighted_default = float(
                (subset["default_rate"] * subset["application_count"]).sum()
                / total_applications
            )
            disbursement_amt = int(subset["disbursement_amt"].sum())

            if zone == STORY_ZONE and quarter == STORY_QUARTER:
                avg_processing_days = 9.0  # tripled from baseline of 3
            elif zone == STORY_ZONE and quarter == STORY_RECOVERY_QUARTER:
                avg_processing_days = 5.0  # partial recovery
            elif zone == STORY_ZONE:
                avg_processing_days = 3.0
            else:
                avg_processing_days = round(_jitter(3.0, 0.15), 1)

            rows.append(
                {
                    "zone": zone,
                    "quarter": quarter,
                    "approval_rate": round(weighted_approval, 1),
                    "rejection_rate": round(100.0 - weighted_approval, 1),
                    "avg_processing_days": avg_processing_days,
                    "default_rate": round(weighted_default, 2),
                    "disbursement_amt": disbursement_amt,
                }
            )
    return pd.DataFrame(rows)


def _value_for_zone_quarter(
    zone: str,
    quarter: str,
    baseline: float,
    *,
    story_value: float,
    recovery_value: float,
    spread: float,
    round_ndigits: int = 1,
) -> float:
    """Resolve a metric value with the planted South-Q3 override applied.

    Args:
        zone: The zone being generated.
        quarter: The quarter being generated.
        baseline: The normal baseline value for this metric.
        story_value: The value to plant for South Q3 2025.
        recovery_value: The value to plant for South Q4 2025 (partial recovery).
        spread: Jitter fraction for non-story zones.
        round_ndigits: Decimal places to round to.

    Returns:
        The resolved metric value.
    """
    if zone == STORY_ZONE and quarter == STORY_QUARTER:
        return round(story_value, round_ndigits)
    if zone == STORY_ZONE and quarter == STORY_RECOVERY_QUARTER:
        return round(recovery_value, round_ndigits)
    if zone == STORY_ZONE:
        return round(baseline, round_ndigits)
    return round(_jitter(baseline, spread), round_ndigits)


def _build_staffing() -> pd.DataFrame:
    """Generate the staffing table with the South-Q3 collapse planted.

    Returns:
        A DataFrame with one row per (zone, quarter).
    """
    rows: list[dict[str, object]] = []
    for zone in ZONES:
        zone_headcount_base = 120 * _ZONE_SIZE_MULTIPLIER[zone]
        for quarter in QUARTERS:
            headcount = _value_for_zone_quarter(
                zone, quarter, zone_headcount_base,
                story_value=zone_headcount_base * 0.78,  # -22%
                recovery_value=zone_headcount_base * 0.85,
                spread=0.03, round_ndigits=0,
            )
            attrition_rate = _value_for_zone_quarter(
                zone, quarter, 8.0,
                story_value=19.0, recovery_value=14.0, spread=0.12,
            )
            training_completion_pct = _value_for_zone_quarter(
                zone, quarter, 89.0,
                story_value=31.0, recovery_value=55.0, spread=0.04,
            )
            open_positions = _value_for_zone_quarter(
                zone, quarter, 3.0,
                story_value=12.0, recovery_value=9.0, spread=0.30, round_ndigits=0,
            )
            avg_tenure_months = _value_for_zone_quarter(
                zone, quarter, 48.0,
                story_value=38.0, recovery_value=40.0, spread=0.05,
            )
            rows.append(
                {
                    "zone": zone,
                    "quarter": quarter,
                    "headcount": int(headcount),
                    "attrition_rate": attrition_rate,
                    "training_completion_pct": training_completion_pct,
                    "open_positions": int(open_positions),
                    "avg_tenure_months": avg_tenure_months,
                }
            )
    return pd.DataFrame(rows)


def _build_customer_metrics() -> pd.DataFrame:
    """Generate the customer_metrics table with the South-Q3 NPS/churn shock.

    Returns:
        A DataFrame with one row per (zone, quarter).
    """
    rows: list[dict[str, object]] = []
    for zone in ZONES:
        complaint_base = 120 * _ZONE_SIZE_MULTIPLIER[zone]
        for quarter in QUARTERS:
            nps_score = _value_for_zone_quarter(
                zone, quarter, 72.0,
                story_value=41.0, recovery_value=52.0, spread=0.05, round_ndigits=0,
            )
            churn_rate = _value_for_zone_quarter(
                zone, quarter, 8.0,
                story_value=18.0, recovery_value=14.0, spread=0.10,
            )
            complaint_count = _value_for_zone_quarter(
                zone, quarter, complaint_base,
                story_value=complaint_base * 3.0, recovery_value=complaint_base * 2.0,
                spread=0.12, round_ndigits=0,
            )
            resolution_time_hrs = _value_for_zone_quarter(
                zone, quarter, 24.0,
                story_value=60.0, recovery_value=40.0, spread=0.10,
            )
            rows.append(
                {
                    "zone": zone,
                    "quarter": quarter,
                    "nps_score": int(nps_score),
                    "churn_rate": churn_rate,
                    "complaint_count": int(complaint_count),
                    "resolution_time_hrs": resolution_time_hrs,
                }
            )
    return pd.DataFrame(rows)


def _build_branch_operations() -> pd.DataFrame:
    """Generate the branch_operations table (four branches per zone).

    Returns:
        A DataFrame with one row per (zone, branch_id, quarter).
    """
    rows: list[dict[str, object]] = []
    for zone in ZONES:
        zone_code = zone[:3].upper()
        for branch_index in range(1, 5):
            branch_id = f"{zone_code}-{branch_index:02d}"
            footfall_base = 8000 * _ZONE_SIZE_MULTIPLIER[zone]
            for quarter in QUARTERS:
                footfall = _value_for_zone_quarter(
                    zone, quarter, footfall_base,
                    story_value=footfall_base * 1.10,
                    recovery_value=footfall_base * 1.03,
                    spread=0.06, round_ndigits=0,
                )
                avg_wait_mins = _value_for_zone_quarter(
                    zone, quarter, 12.0,
                    story_value=16.8,  # +40%
                    recovery_value=14.0, spread=0.10,
                )
                downtime_hrs = _value_for_zone_quarter(
                    zone, quarter, 5.0,
                    story_value=7.0, recovery_value=6.0, spread=0.20,
                )
                transactions_processed = _value_for_zone_quarter(
                    zone, quarter, 45000 * _ZONE_SIZE_MULTIPLIER[zone],
                    story_value=45000 * _ZONE_SIZE_MULTIPLIER[zone] * 0.97,
                    recovery_value=45000 * _ZONE_SIZE_MULTIPLIER[zone],
                    spread=0.05, round_ndigits=0,
                )
                rows.append(
                    {
                        "zone": zone,
                        "branch_id": branch_id,
                        "quarter": quarter,
                        "footfall": int(footfall),
                        "avg_wait_mins": avg_wait_mins,
                        "downtime_hrs": downtime_hrs,
                        "transactions_processed": int(transactions_processed),
                    }
                )
    return pd.DataFrame(rows)


def _build_risk_metrics() -> pd.DataFrame:
    """Generate the risk_metrics table with the South-Q3 NPA/provisioning rise.

    South Q2->Q3 provisioning rises by ₹1.8 Cr (30M -> 48M), the planted NPA
    exposure figure.

    Returns:
        A DataFrame with one row per (zone, quarter).
    """
    rows: list[dict[str, object]] = []
    for zone in ZONES:
        provisioning_base = 30_000_000 * _ZONE_SIZE_MULTIPLIER[zone]
        for quarter in QUARTERS:
            npa_rate = _value_for_zone_quarter(
                zone, quarter, 3.0,
                story_value=4.5, recovery_value=4.2, spread=0.10, round_ndigits=2,
            )
            fraud_cases = _value_for_zone_quarter(
                zone, quarter, 5.0,
                story_value=9.0, recovery_value=7.0, spread=0.25, round_ndigits=0,
            )
            compliance_flags = _value_for_zone_quarter(
                zone, quarter, 4.0,
                story_value=14.0, recovery_value=10.0, spread=0.30, round_ndigits=0,
            )
            audit_score = _value_for_zone_quarter(
                zone, quarter, 88.0,
                story_value=72.0, recovery_value=78.0, spread=0.04, round_ndigits=0,
            )
            # Story provisioning rises by exactly ₹1.8 Cr vs the South baseline.
            provisioning_amt = _value_for_zone_quarter(
                zone, quarter, provisioning_base,
                story_value=provisioning_base + 1.8 * CRORE,
                recovery_value=provisioning_base + 1.4 * CRORE,
                spread=0.05, round_ndigits=0,
            )
            rows.append(
                {
                    "zone": zone,
                    "quarter": quarter,
                    "npa_rate": npa_rate,
                    "fraud_cases": int(fraud_cases),
                    "compliance_flags": int(compliance_flags),
                    "audit_score": int(audit_score),
                    "provisioning_amt": int(provisioning_amt),
                }
            )
    return pd.DataFrame(rows)


def _build_event_log() -> pd.DataFrame:
    """Generate the event_log table including the Aug-14 triggering event.

    The Critical South resignation on 2025-08-14 is the smoking gun; supporting
    and ambient events add realism without competing for primacy.

    Returns:
        A DataFrame with one row per event.
    """
    events: list[dict[str, object]] = [
        # --- The triggering event (the smoking gun) ---
        {
            "event_id": "EVT-2025-0814-STH",
            "date": "2025-08-14",
            "zone": "South",
            "event_type": "resignation",
            "description": (
                "3 senior underwriters resigned simultaneously from the South zone "
                "Personal Loan desk, removing the bulk of senior credit-approval capacity."
            ),
            "severity": "Critical",
            "affected_headcount": 3,
            "affected_product": "Personal Loan",
        },
        # --- Direct downstream consequence ---
        {
            "event_id": "EVT-2025-0820-STH",
            "date": "2025-08-20",
            "zone": "South",
            "event_type": "training_suspended",
            "description": (
                "Underwriter onboarding and training program suspended in South zone; "
                "remaining staff redeployed to clear the Personal Loan backlog."
            ),
            "severity": "High",
            "affected_headcount": 18,
            "affected_product": "Personal Loan",
        },
        # --- Ambient / unrelated events across zones (noise) ---
        {
            "event_id": "EVT-2025-0205-NTH",
            "date": "2025-02-05",
            "zone": "North",
            "event_type": "policy_change",
            "description": "Revised KYC documentation checklist rolled out for Home Loans.",
            "severity": "Low",
            "affected_headcount": 0,
            "affected_product": "Home Loan",
        },
        {
            "event_id": "EVT-2025-0418-WST",
            "date": "2025-04-18",
            "zone": "West",
            "event_type": "system_outage",
            "description": "Core banking system outage for 4 hours during scheduled maintenance.",
            "severity": "Medium",
            "affected_headcount": 0,
            "affected_product": "Auto Loan",
        },
        {
            "event_id": "EVT-2025-0612-EST",
            "date": "2025-06-12",
            "zone": "East",
            "event_type": "audit",
            "description": "Routine internal compliance audit completed with no major findings.",
            "severity": "Low",
            "affected_headcount": 0,
            "affected_product": "Business Loan",
        },
        {
            "event_id": "EVT-2025-0722-CTL",
            "date": "2025-07-22",
            "zone": "Central",
            "event_type": "leadership_change",
            "description": "Planned retirement and succession of the Central zone operations head.",
            "severity": "Medium",
            "affected_headcount": 1,
            "affected_product": "Home Loan",
        },
        {
            "event_id": "EVT-2025-0909-NTH",
            "date": "2025-09-09",
            "zone": "North",
            "event_type": "training",
            "description": "Quarterly refresher training completed for all credit officers.",
            "severity": "Low",
            "affected_headcount": 0,
            "affected_product": "Personal Loan",
        },
        {
            "event_id": "EVT-2025-1003-WST",
            "date": "2025-10-03",
            "zone": "West",
            "event_type": "policy_change",
            "description": "Auto Loan interest-rate slab revised in line with central bank guidance.",
            "severity": "Low",
            "affected_headcount": 0,
            "affected_product": "Auto Loan",
        },
    ]
    return pd.DataFrame(events)


def _write_csv(frame: pd.DataFrame, file_name: str) -> Path:
    """Write a DataFrame to the output directory as CSV.

    Args:
        frame: The DataFrame to persist.
        file_name: Destination file name within the data directory.

    Returns:
        The absolute path of the written file.
    """
    destination = OUTPUT_DIR / file_name
    frame.to_csv(destination, index=False)
    return destination


def _print_summary(frames: dict[str, pd.DataFrame]) -> None:
    """Print a Rich summary table of generated datasets and the planted story.

    Args:
        frames: Mapping of file name to generated DataFrame.
    """
    table = Table(title="BankIQ synthetic datasets generated", show_lines=False)
    table.add_column("Dataset", style="cyan", no_wrap=True)
    table.add_column("Rows", justify="right", style="green")
    table.add_column("Columns", style="magenta")
    for file_name, frame in frames.items():
        table.add_row(file_name, str(len(frame)), ", ".join(frame.columns))
    console.print(table)

    # Confirm the headline planted figures for quick verification.
    product = frames["product_performance.csv"]
    personal_south = product[
        (product["zone"] == "South") & (product["product_type"] == "Personal Loan")
    ].set_index("quarter")["disbursement_amt"]
    lost_cr = (personal_south["Q2 2025"] - personal_south["Q3 2025"]) / CRORE

    console.print(
        f"\n[bold]Planted South Q3 story check[/bold]\n"
        f"  Personal-Loan disbursement Q2 -> Q3: "
        f"₹{personal_south['Q2 2025'] / CRORE:.2f} Cr -> "
        f"₹{personal_south['Q3 2025'] / CRORE:.2f} Cr "
        f"([red]-₹{lost_cr:.2f} Cr[/red])\n"
        f"  Plus ₹1.80 Cr NPA provisioning rise = "
        f"[bold red]₹{lost_cr + 1.8:.2f} Cr total 30-day exposure[/bold red]"
    )


def main() -> None:
    """Generate all seven datasets and write them to ``backend/data/``."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    console.rule("[bold cyan]Generating BankIQ synthetic banking datasets")

    product_performance = _build_product_performance()
    loan_performance = _build_loan_performance(product_performance)

    frames: dict[str, pd.DataFrame] = {
        "loan_performance.csv": loan_performance,
        "customer_metrics.csv": _build_customer_metrics(),
        "branch_operations.csv": _build_branch_operations(),
        "staffing.csv": _build_staffing(),
        "risk_metrics.csv": _build_risk_metrics(),
        "product_performance.csv": product_performance,
        "event_log.csv": _build_event_log(),
    }

    for file_name, frame in frames.items():
        path = _write_csv(frame, file_name)
        console.print(f"  [green]wrote[/green] {path}")

    _print_summary(frames)
    console.rule("[bold green]Done")


if __name__ == "__main__":
    main()
