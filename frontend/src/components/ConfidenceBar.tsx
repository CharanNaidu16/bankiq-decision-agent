/** Horizontal bar visualizing a confidence score in [0, 1]. */

import styles from "../styles/ConfidenceBar.module.css";

interface ConfidenceBarProps {
  confidence: number;
  label?: string;
}

/**
 * Choose a qualitative tone class for a confidence value.
 *
 * @param confidence - Confidence score in [0, 1].
 * @returns A CSS module class name for the fill color.
 */
function toneForConfidence(confidence: number): string {
  if (confidence >= 0.75) {
    return styles.high;
  }
  if (confidence >= 0.5) {
    return styles.medium;
  }
  return styles.low;
}

/**
 * Render a labeled confidence bar.
 *
 * @param props - The confidence value and an optional label.
 * @returns The confidence bar element.
 */
export function ConfidenceBar({ confidence, label }: ConfidenceBarProps): JSX.Element {
  const clamped = Math.max(0, Math.min(1, confidence));
  const percent = Math.round(clamped * 100);
  return (
    <div className={styles.wrapper}>
      {label && <span className={styles.label}>{label}</span>}
      <div className={styles.track}>
        <div className={`${styles.fill} ${toneForConfidence(clamped)}`} style={{ width: `${percent}%` }} />
      </div>
      <span className={styles.value}>{percent}%</span>
    </div>
  );
}
