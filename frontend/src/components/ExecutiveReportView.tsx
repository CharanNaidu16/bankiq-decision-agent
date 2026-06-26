/** Renders the full board-ready executive report as structured sections. */

import type { FinalReport, ReportSection as ReportSectionModel } from "../types/investigation";
import { ConfidenceBar } from "./ConfidenceBar";
import { CopyButton } from "./CopyButton";
import { EmailReportButton } from "./EmailReportButton";
import { RecommendedActionsTable } from "./RecommendedActionsTable";
import { ReportSection } from "./ReportSection";
import { buildReportPlainText } from "../utils/buildReportPlainText";
import styles from "../styles/ExecutiveReportView.module.css";

interface ExecutiveReportViewProps {
  finalReport: FinalReport;
}

/**
 * Format a money figure in ₹ Cr.
 *
 * @param valueCr - The value already expressed in crores of rupees.
 * @returns A formatted string like "₹4.2 Cr".
 */
function formatCrore(valueCr: number): string {
  return `₹${valueCr.toFixed(2)} Cr`;
}

/**
 * Whether a report section has anything worth rendering.
 *
 * Lightweight paths (a simple answer, an out-of-scope decline, a guardrail
 * refusal) reuse the executive-report shape but leave the analytical sections
 * empty. Rendering those as bare headings looks broken, so we skip them.
 *
 * @param section - The section to test.
 * @returns True when the section has body text or bullet points.
 */
function hasContent(section: ReportSectionModel): boolean {
  return Boolean(section.body) || section.bullets.length > 0;
}

/**
 * Render the executive report, including causal chain and financial projections.
 *
 * @param props - The terminal final report from the pipeline.
 * @returns The report view element.
 */
export function ExecutiveReportView({ finalReport }: ExecutiveReportViewProps): JSX.Element {
  const { report, root_cause_result: rootCause, impact_result: impact } = finalReport;

  return (
    <article className={styles.report}>
      {report.degraded_notice && (
        <div className={styles.degradedBanner} role="alert">
          ⚠ {report.degraded_notice}
        </div>
      )}

      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>{report.title}</h2>
          <p className={styles.meta}>
            Completed in {(finalReport.duration_ms / 1000).toFixed(1)}s
            {report.confidence_statement && ` · ${report.confidence_statement}`}
          </p>
        </div>
        <div className={styles.actions}>
          <CopyButton getText={() => buildReportPlainText(finalReport)} />
          <EmailReportButton
            getText={() => buildReportPlainText(finalReport)}
            subject={report.title}
          />
        </div>
      </header>

      <div className={styles.summaryCallout}>
        <span className={styles.summaryLabel}>Executive Summary</span>
        <p className={styles.summaryText}>{report.executive_summary}</p>
      </div>

      {impact && impact.headline_total_exposure_cr > 0 && (
        <div className={styles.headlineGrid}>
          <div className={styles.headlineCard}>
            <span className={styles.headlineLabel}>Total Exposure (30 days)</span>
            <span className={styles.headlineValue}>
              {formatCrore(impact.headline_total_exposure_cr)}
            </span>
          </div>
          {impact.customer_lifetime_value_lost_cr > 0 && (
            <div className={styles.headlineCard}>
              <span className={styles.headlineLabel}>Customer Lifetime Value Lost</span>
              <span className={styles.headlineValue}>
                {formatCrore(impact.customer_lifetime_value_lost_cr)}
              </span>
            </div>
          )}
        </div>
      )}

      {hasContent(report.what_happened) && (
        <ReportSection section={report.what_happened} accent="01" />
      )}
      {hasContent(report.triggering_event) && (
        <ReportSection section={report.triggering_event} accent="02" />
      )}

      {(hasContent(report.why_it_happened) ||
        (rootCause && rootCause.causal_chain.links.length > 0)) && (
        <div className={styles.sectionBlock}>
          {hasContent(report.why_it_happened) && (
            <ReportSection section={report.why_it_happened} accent="03" />
          )}
          {rootCause && rootCause.causal_chain.links.length > 0 && (
          <div className={styles.causalChain}>
            <span className={styles.causalLabel}>
              Causal Chain · overall confidence
            </span>
            <ConfidenceBar confidence={rootCause.causal_chain.overall_confidence} />
            <ol className={styles.causalList}>
              {rootCause.causal_chain.links.map((link) => (
                <li key={link.sequence} className={styles.causalItem}>
                  <div className={styles.causalText}>
                    <strong>{link.cause}</strong>
                    <span className={styles.arrow}>→</span>
                    <span>{link.effect}</span>
                  </div>
                  <p className={styles.evidence}>{link.evidence}</p>
                  <ConfidenceBar confidence={link.confidence} label="confidence" />
                </li>
              ))}
            </ol>
          </div>
        )}
        </div>
      )}

      {(hasContent(report.financial_impact) ||
        (impact && impact.projections.length > 0)) && (
        <div className={styles.sectionBlock}>
          {hasContent(report.financial_impact) && (
            <ReportSection section={report.financial_impact} accent="04" />
          )}
          {impact && impact.projections.length > 0 && (
          <div className={styles.tableWrapper}>
            <table className={styles.projectionTable}>
              <thead>
                <tr>
                  <th>Horizon</th>
                  <th>Revenue at Risk</th>
                  <th>NPA Exposure</th>
                  <th>Total Exposure</th>
                </tr>
              </thead>
              <tbody>
                {impact.projections.map((projection) => (
                  <tr key={projection.horizon_days}>
                    <td>{projection.horizon_days} days</td>
                    <td>{formatCrore(projection.revenue_at_risk_cr)}</td>
                    <td>{formatCrore(projection.npa_exposure_cr)}</td>
                    <td>
                      <strong>{formatCrore(projection.total_exposure_cr)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </div>
      )}

      {report.recommended_actions.length > 0 && (
        <div className={styles.sectionBlock}>
          <h3 className={styles.actionsHeading}>
            <span className={styles.accent}>05</span>Recommended Actions
          </h3>
          <RecommendedActionsTable actions={report.recommended_actions} />
        </div>
      )}
    </article>
  );
}
