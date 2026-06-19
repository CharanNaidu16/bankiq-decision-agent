/**
 * Convert a FinalReport into a clean, copy-paste-friendly plain-text report.
 *
 * Used by the copy-to-clipboard action so executives can paste the report into
 * email or a document without any UI markup.
 */

import type { FinalReport, ReportSection } from "../types/investigation";

/**
 * Render one section as a plain-text block.
 *
 * @param section - The report section to render.
 * @returns The section as plain text, including any bullets.
 */
function renderSection(section: ReportSection): string {
  const lines: string[] = [section.heading.toUpperCase(), section.body];
  for (const bullet of section.bullets) {
    lines.push(`  - ${bullet}`);
  }
  return lines.filter((line) => line.length > 0).join("\n");
}

/**
 * Build the full plain-text representation of a final report.
 *
 * @param finalReport - The terminal report from the pipeline.
 * @returns A formatted plain-text string suitable for copying.
 */
export function buildReportPlainText(finalReport: FinalReport): string {
  const { report, impact_result: impact, root_cause_result: rootCause } = finalReport;
  const blocks: string[] = [];

  blocks.push(report.title);
  blocks.push("=".repeat(report.title.length));
  blocks.push(`Question: ${finalReport.question}`);
  blocks.push("");
  blocks.push("EXECUTIVE SUMMARY");
  blocks.push(report.executive_summary);
  blocks.push("");
  blocks.push(renderSection(report.what_happened));
  blocks.push("");
  blocks.push(renderSection(report.triggering_event));
  blocks.push("");
  blocks.push(renderSection(report.why_it_happened));

  if (rootCause && rootCause.causal_chain.links.length > 0) {
    blocks.push("");
    blocks.push("CAUSAL CHAIN");
    for (const link of rootCause.causal_chain.links) {
      const confidencePct = Math.round(link.confidence * 100);
      blocks.push(`  ${link.sequence}. ${link.cause} -> ${link.effect} (${confidencePct}%)`);
    }
  }

  blocks.push("");
  blocks.push(renderSection(report.financial_impact));

  if (impact && impact.projections.length > 0) {
    blocks.push("");
    blocks.push("FINANCIAL PROJECTIONS (₹ Cr)");
    for (const projection of impact.projections) {
      blocks.push(
        `  ${projection.horizon_days}d: revenue ₹${projection.revenue_at_risk_cr.toFixed(2)} Cr` +
          ` + NPA ₹${projection.npa_exposure_cr.toFixed(2)} Cr` +
          ` = ₹${projection.total_exposure_cr.toFixed(2)} Cr`,
      );
    }
  }

  if (report.recommended_actions.length > 0) {
    blocks.push("");
    blocks.push("RECOMMENDED ACTIONS");
    report.recommended_actions.forEach((action, index) => {
      blocks.push(`  ${index + 1}. [${action.priority.toUpperCase()}] ${action.title}`);
      blocks.push(`     ${action.description}`);
      blocks.push(`     Owner: ${action.owner} | Timeline: ${action.timeline}`);
      blocks.push(`     Expected: ${action.expected_outcome}`);
    });
  }

  if (report.confidence_statement) {
    blocks.push("");
    blocks.push(`Confidence: ${report.confidence_statement}`);
  }

  return blocks.join("\n");
}
