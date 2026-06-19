/** Table of recommended actions with owner, timeline, and expected outcome. */

import type { RecommendedAction } from "../types/investigation";
import styles from "../styles/RecommendedActionsTable.module.css";

interface RecommendedActionsTableProps {
  actions: RecommendedAction[];
}

/**
 * Map a priority string to a CSS module class for its pill.
 *
 * @param priority - The action priority (e.g. "high").
 * @returns A CSS module class name.
 */
function priorityClass(priority: string): string {
  const normalized = priority.toLowerCase();
  if (normalized === "high") {
    return styles.high;
  }
  if (normalized === "medium") {
    return styles.medium;
  }
  return styles.low;
}

/**
 * Render the recommended actions as a structured table.
 *
 * @param props - The list of recommended actions.
 * @returns The table element, or an empty-state note when there are none.
 */
export function RecommendedActionsTable({
  actions,
}: RecommendedActionsTableProps): JSX.Element {
  if (actions.length === 0) {
    return <p className={styles.empty}>No recommended actions were generated.</p>;
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Action</th>
            <th>Owner</th>
            <th>Timeline</th>
            <th>Expected Outcome</th>
            <th>Priority</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action, index) => (
            <tr key={index}>
              <td>
                <strong>{action.title}</strong>
                <span className={styles.actionDescription}>{action.description}</span>
              </td>
              <td>{action.owner}</td>
              <td>{action.timeline}</td>
              <td>{action.expected_outcome}</td>
              <td>
                <span className={`${styles.priority} ${priorityClass(action.priority)}`}>
                  {action.priority}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
