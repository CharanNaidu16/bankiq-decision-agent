"""Centralized, immutable constants for the BankIQ backend.

Every threshold, canonical name, and magic number used across the application
lives here so that business logic never embeds bare literals. Anything that is
operator-tunable at deploy time (keys, model id, host/port) belongs in
``config.py`` instead; this module holds values that are intrinsic to the
domain and the agent contract.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Agent identifiers (stable keys shared between backend pipeline and frontend
# progress tracker). Order here defines pipeline execution order.
# ---------------------------------------------------------------------------
AGENT_NAME_INTENT: Final[str] = "intent"
AGENT_NAME_DATA_ANALYST: Final[str] = "data_analyst"
AGENT_NAME_ROOT_CAUSE: Final[str] = "root_cause"
AGENT_NAME_IMPACT_FORECAST: Final[str] = "impact_forecast"
AGENT_NAME_EXECUTIVE_REPORT: Final[str] = "executive_report"

ORDERED_AGENT_NAMES: Final[tuple[str, ...]] = (
    AGENT_NAME_INTENT,
    AGENT_NAME_DATA_ANALYST,
    AGENT_NAME_ROOT_CAUSE,
    AGENT_NAME_IMPACT_FORECAST,
    AGENT_NAME_EXECUTIVE_REPORT,
)

# Triage/router and lightweight-path agents. These run instead of (not within)
# the ordered investigation pipeline above, so they are intentionally kept out
# of ``ORDERED_AGENT_NAMES`` (which defines the five-step investigation UI).
AGENT_NAME_TRIAGE: Final[str] = "triage"
AGENT_NAME_SIMPLE_QUERY: Final[str] = "simple_query"
AGENT_NAME_GENERAL_ASSISTANT: Final[str] = "general_assistant"

# Human-friendly labels rendered in logs and the UI.
AGENT_DISPLAY_NAMES: Final[dict[str, str]] = {
    AGENT_NAME_INTENT: "Intent Agent",
    AGENT_NAME_DATA_ANALYST: "Data Analyst Agent",
    AGENT_NAME_ROOT_CAUSE: "Root Cause Agent",
    AGENT_NAME_IMPACT_FORECAST: "Impact Forecast Agent",
    AGENT_NAME_EXECUTIVE_REPORT: "Executive Report Agent",
    AGENT_NAME_TRIAGE: "Triage Router",
    AGENT_NAME_SIMPLE_QUERY: "Quick Answer",
    AGENT_NAME_GENERAL_ASSISTANT: "BankIQ Assistant",
}

# ---------------------------------------------------------------------------
# Dataset identifiers and CSV file names (the seven synthetic tables).
# ---------------------------------------------------------------------------
DATASET_LOAN_PERFORMANCE: Final[str] = "loan_performance"
DATASET_CUSTOMER_METRICS: Final[str] = "customer_metrics"
DATASET_BRANCH_OPERATIONS: Final[str] = "branch_operations"
DATASET_STAFFING: Final[str] = "staffing"
DATASET_RISK_METRICS: Final[str] = "risk_metrics"
DATASET_PRODUCT_PERFORMANCE: Final[str] = "product_performance"
DATASET_EVENT_LOG: Final[str] = "event_log"

DATASET_FILE_NAMES: Final[dict[str, str]] = {
    DATASET_LOAN_PERFORMANCE: "loan_performance.csv",
    DATASET_CUSTOMER_METRICS: "customer_metrics.csv",
    DATASET_BRANCH_OPERATIONS: "branch_operations.csv",
    DATASET_STAFFING: "staffing.csv",
    DATASET_RISK_METRICS: "risk_metrics.csv",
    DATASET_PRODUCT_PERFORMANCE: "product_performance.csv",
    DATASET_EVENT_LOG: "event_log.csv",
}

ALL_DATASET_NAMES: Final[tuple[str, ...]] = tuple(DATASET_FILE_NAMES.keys())

# ---------------------------------------------------------------------------
# Domain dimensions.
# ---------------------------------------------------------------------------
ZONE_NORTH: Final[str] = "North"
ZONE_SOUTH: Final[str] = "South"
ZONE_EAST: Final[str] = "East"
ZONE_WEST: Final[str] = "West"
ZONE_CENTRAL: Final[str] = "Central"
ZONE_NORTHWEST: Final[str] = "Northwest"
ZONE_SOUTHEAST: Final[str] = "Southeast"
ALL_ZONES: Final[tuple[str, ...]] = (
    ZONE_NORTH,
    ZONE_SOUTH,
    ZONE_EAST,
    ZONE_WEST,
    ZONE_CENTRAL,
    ZONE_NORTHWEST,
    ZONE_SOUTHEAST,
)

QUARTER_Q1: Final[str] = "Q1 2025"
QUARTER_Q2: Final[str] = "Q2 2025"
QUARTER_Q3: Final[str] = "Q3 2025"
QUARTER_Q4: Final[str] = "Q4 2025"
ALL_QUARTERS: Final[tuple[str, ...]] = (QUARTER_Q1, QUARTER_Q2, QUARTER_Q3, QUARTER_Q4)

PRODUCT_HOME_LOAN: Final[str] = "Home Loan"
PRODUCT_PERSONAL_LOAN: Final[str] = "Personal Loan"
PRODUCT_BUSINESS_LOAN: Final[str] = "Business Loan"
PRODUCT_AUTO_LOAN: Final[str] = "Auto Loan"
ALL_PRODUCT_TYPES: Final[tuple[str, ...]] = (
    PRODUCT_HOME_LOAN,
    PRODUCT_PERSONAL_LOAN,
    PRODUCT_BUSINESS_LOAN,
    PRODUCT_AUTO_LOAN,
)

EVENT_SEVERITY_LOW: Final[str] = "Low"
EVENT_SEVERITY_MEDIUM: Final[str] = "Medium"
EVENT_SEVERITY_HIGH: Final[str] = "High"
EVENT_SEVERITY_CRITICAL: Final[str] = "Critical"
ALL_EVENT_SEVERITIES: Final[tuple[str, ...]] = (
    EVENT_SEVERITY_LOW,
    EVENT_SEVERITY_MEDIUM,
    EVENT_SEVERITY_HIGH,
    EVENT_SEVERITY_CRITICAL,
)

# ---------------------------------------------------------------------------
# Anomaly detection thresholds (used to instruct the analyst agent what counts
# as material). All expressed as positive percentages unless noted.
# ---------------------------------------------------------------------------
APPROVAL_RATE_DROP_THRESHOLD_PCT: Final[float] = 5.0
NPS_DROP_THRESHOLD_POINTS: Final[float] = 8.0
CHURN_RATE_SPIKE_THRESHOLD_PCT: Final[float] = 15.0
PROCESSING_DAYS_INCREASE_THRESHOLD_PCT: Final[float] = 25.0
TRAINING_COMPLETION_DROP_THRESHOLD_PCT: Final[float] = 20.0
HEADCOUNT_DROP_THRESHOLD_PCT: Final[float] = 10.0
WAIT_TIME_INCREASE_THRESHOLD_PCT: Final[float] = 20.0
NPA_RATE_INCREASE_THRESHOLD_PCT: Final[float] = 10.0
GENERIC_MATERIALITY_THRESHOLD_PCT: Final[float] = 10.0

# Minimum confidence (0-1) for a causal link to be treated as established
# rather than speculative.
CAUSAL_LINK_MIN_CONFIDENCE: Final[float] = 0.5

# ---------------------------------------------------------------------------
# Financial constants.
# ---------------------------------------------------------------------------
# One crore = 10,000,000 rupees. Used to convert raw rupee figures into ₹ Cr.
CRORE_IN_RUPEES: Final[int] = 10_000_000
CURRENCY_SYMBOL: Final[str] = "₹"
CURRENCY_CRORE_SUFFIX: Final[str] = "Cr"

# Forecast horizons (days) over which unaddressed impact is projected.
FORECAST_HORIZON_DAYS: Final[tuple[int, ...]] = (30, 60, 90)

# ---------------------------------------------------------------------------
# LLM interaction constants.
# ---------------------------------------------------------------------------
# One bounded retry when the model returns text that does not parse as the
# expected JSON schema.
LLM_JSON_PARSE_MAX_RETRIES: Final[int] = 1
# Cap on the response token budget for a single agent call. Kept modest because
# the reserved output budget counts against the provider's tokens-per-minute
# limit (Groq free tier allows ~12k TPM); a large reservation plus the prompt can
# exceed that and trigger a 413/429. Downstream agents receive a *compact*
# analysis summary (see AnalysisResult.to_prompt_json) rather than every anomaly,
# so this budget is comfortably sufficient for every stage's output.
LLM_MAX_OUTPUT_TOKENS: Final[int] = 4096

# ---------------------------------------------------------------------------
# SSE event type names emitted on the wire.
# ---------------------------------------------------------------------------
SSE_EVENT_AGENT_PROGRESS: Final[str] = "agent_progress"
SSE_EVENT_REPORT: Final[str] = "report"
SSE_EVENT_DONE: Final[str] = "done"
SSE_EVENT_ERROR: Final[str] = "error"

# ---------------------------------------------------------------------------
# Guardrail messaging. These are fixed, server-controlled strings — never
# model-generated — so a crafted prompt cannot coax a harmful or leaky reply.
# ---------------------------------------------------------------------------
# Returned when triage classifies a request as a guardrail violation (attempts
# to delete/modify/write data, change the app/code/config, or override the
# system's instructions).
REJECTION_MESSAGE: Final[str] = (
    "BankIQ is a read-only banking analytics assistant. It cannot modify, "
    "delete, or write data, change the application or its configuration, or "
    "follow instructions that override its operating rules. Please ask a "
    "question about the banking KPIs and datasets, and BankIQ will investigate."
)

# Returned for general questions that fall outside banking, finance, and
# economics. The general-assistant agent is instructed to answer with this.
OUT_OF_SCOPE_DECLINE_MESSAGE: Final[str] = (
    "That question is outside BankIQ's area. BankIQ helps with banking, "
    "finance, and economics — for example loan performance, NPS, churn, NPA, "
    "and the drivers behind KPI movements. Ask about one of those and BankIQ "
    "will help."
)

# Returned when the triage step itself cannot run because the language model is
# unavailable (e.g. rate-limited, quota exhausted, or misconfigured). In that
# state we have no classification signal, so rather than fan out to the full
# five-agent pipeline — which would fire five more doomed LLM calls — BankIQ
# returns this single, honest message and asks the user to retry.
SERVICE_UNAVAILABLE_MESSAGE: Final[str] = (
    "BankIQ could not process this request right now because its language model "
    "is temporarily unavailable — usually a rate limit or exhausted API quota. "
    "Please wait a moment and try again. If this keeps happening, check the "
    "GROQ_API_KEY and model quota in the server configuration."
)
