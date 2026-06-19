/** Small status indicator (icon + label) for a single agent. */

import type { AgentStatus } from "../types/investigation";
import styles from "../styles/AgentStatusBadge.module.css";

interface AgentStatusBadgeProps {
  status: AgentStatus;
}

const STATUS_ICON: Record<AgentStatus, string> = {
  pending: "○",
  running: "◐",
  completed: "✓",
  failed: "✕",
};

const STATUS_LABEL: Record<AgentStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
};

/**
 * Render a colored badge reflecting an agent's lifecycle status.
 *
 * @param props - The status to render.
 * @returns The badge element.
 */
export function AgentStatusBadge({ status }: AgentStatusBadgeProps): JSX.Element {
  return (
    <span className={`${styles.badge} ${styles[status]}`}>
      <span className={status === "running" ? styles.spin : undefined}>
        {STATUS_ICON[status]}
      </span>
      {STATUS_LABEL[status]}
    </span>
  );
}
