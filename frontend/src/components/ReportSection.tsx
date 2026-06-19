/** A titled report section with body text and optional bullets. */

import type { ReportSection as ReportSectionModel } from "../types/investigation";
import styles from "../styles/ReportSection.module.css";

interface ReportSectionProps {
  section: ReportSectionModel;
  accent?: string;
}

/**
 * Render one titled section of the executive report.
 *
 * @param props - The section model and an optional accent label.
 * @returns The section element.
 */
export function ReportSection({ section, accent }: ReportSectionProps): JSX.Element {
  return (
    <section className={styles.section}>
      <h3 className={styles.heading}>
        {accent && <span className={styles.accent}>{accent}</span>}
        {section.heading}
      </h3>
      {section.body && <p className={styles.body}>{section.body}</p>}
      {section.bullets.length > 0 && (
        <ul className={styles.bullets}>
          {section.bullets.map((bullet, index) => (
            <li key={index}>{bullet}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
