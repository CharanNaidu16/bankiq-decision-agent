/**
 * TypeScript mirrors of the backend Pydantic contracts.
 *
 * Keep these in sync with `backend/app/models/*`. Only the fields the UI reads
 * are typed strictly; everything the backend sends is otherwise compatible.
 */

/** Lifecycle status of a single agent (mirrors backend AgentStatus). */
export type AgentStatus = "pending" | "running" | "completed" | "failed";

/** Stable agent identifiers (mirror backend constants.ORDERED_AGENT_NAMES). */
export type AgentName =
  | "intent"
  | "data_analyst"
  | "root_cause"
  | "impact_forecast"
  | "executive_report";

/** A progress update emitted as an agent starts, completes, or fails. */
export interface AgentProgressEvent {
  agent_name: AgentName;
  display_name: string;
  status: AgentStatus;
  message: string;
  step_index: number;
  total_steps: number;
  elapsed_ms: number | null;
}

export interface ParsedIntent {
  primary_kpi: string;
  focus_zone: string | null;
  focus_quarter: string | null;
  comparison_quarter: string | null;
  focus_product: string | null;
  target_datasets: string[];
  normalized_question: string;
  interpretation_notes: string;
}

export interface CausalLink {
  sequence: number;
  cause: string;
  effect: string;
  evidence: string;
  confidence: number;
  supporting_datasets: string[];
}

export interface CausalChain {
  links: CausalLink[];
  narrative: string;
  overall_confidence: number;
}

export interface TriggeringEvent {
  event_id: string | null;
  date: string | null;
  zone: string | null;
  event_type: string | null;
  description: string;
  severity: string | null;
  affected_product: string | null;
  rationale: string;
}

export interface RootCauseResult {
  triggering_event: TriggeringEvent | null;
  causal_chain: CausalChain;
  primary_root_cause: string;
  degraded: boolean;
}

export interface ImpactProjection {
  horizon_days: number;
  revenue_at_risk_cr: number;
  npa_exposure_cr: number;
  total_exposure_cr: number;
  assumptions: string;
}

export interface ProductImpact {
  product: string;
  disbursement_at_risk_cr: number;
  commentary: string;
}

export interface ImpactResult {
  projections: ImpactProjection[];
  product_impacts: ProductImpact[];
  customer_lifetime_value_lost_cr: number;
  headline_total_exposure_cr: number;
  summary: string;
  degraded: boolean;
}

export interface ReportSection {
  heading: string;
  body: string;
  bullets: string[];
}

export interface RecommendedAction {
  title: string;
  description: string;
  owner: string;
  timeline: string;
  expected_outcome: string;
  priority: string;
}

export interface ExecutiveReport {
  title: string;
  executive_summary: string;
  what_happened: ReportSection;
  triggering_event: ReportSection;
  why_it_happened: ReportSection;
  financial_impact: ReportSection;
  recommended_actions: RecommendedAction[];
  confidence_statement: string;
  degraded_notice: string | null;
}

export interface FinalReport {
  question: string;
  report: ExecutiveReport;
  parsed_intent: ParsedIntent | null;
  root_cause_result: RootCauseResult | null;
  impact_result: ImpactResult | null;
  degraded: boolean;
  duration_ms: number;
}
