/** Live rail showing the five agents executing in sequence. */

import type { AgentRunState } from "../hooks/useInvestigation";
import { AgentStatusBadge } from "./AgentStatusBadge";
import styles from "../styles/AgentProgressTracker.module.css";

interface AgentProgressTrackerProps {
  agentStates: AgentRunState[];
}

/**
 * Format an elapsed duration in milliseconds for display.
 *
 * @param elapsedMs - Elapsed time in milliseconds, or null if not finished.
 * @returns A human-friendly duration string, or an empty string.
 */
function formatElapsed(elapsedMs: number | null): string {
  if (elapsedMs === null) {
    return "";
  }
  return elapsedMs >= 1000 ? `${(elapsedMs / 1000).toFixed(1)}s` : `${Math.round(elapsedMs)}ms`;
}

/**
 * Render the vertical agent progress tracker.
 *
 * @param props - The ordered agent run-states.
 * @returns The tracker element.
 */
export function AgentProgressTracker({ agentStates }: AgentProgressTrackerProps): JSX.Element {
  return (
    <section className={styles.tracker} aria-label="Agent pipeline progress">
      <h2 className={styles.title}>Investigation Pipeline</h2>
      <ol className={styles.list}>
        {agentStates.map((agentState, index) => (
          <li
            key={agentState.name}
            className={`${styles.item} ${styles[agentState.status]}`}
          >
            <div className={styles.rail}>
              <span className={styles.stepNumber}>{index + 1}</span>
              {index < agentStates.length - 1 && <span className={styles.connector} />}
            </div>
            <div className={styles.body}>
              <div className={styles.headerRow}>
                <span className={styles.agentName}>{agentState.displayName}</span>
                <AgentStatusBadge status={agentState.status} />
              </div>
              <p className={styles.message}>{agentState.message}</p>
              {agentState.elapsedMs !== null && (
                <span className={styles.elapsed}>{formatElapsed(agentState.elapsedMs)}</span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
