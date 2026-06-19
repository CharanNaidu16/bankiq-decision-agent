/** Button that copies provided text to the clipboard with transient feedback. */

import { useState } from "react";

import styles from "../styles/CopyButton.module.css";

interface CopyButtonProps {
  getText: () => string;
  label?: string;
}

const FEEDBACK_RESET_MS = 2000;

/**
 * Render a copy-to-clipboard button that confirms success briefly.
 *
 * @param props - A lazy text provider and an optional button label.
 * @returns The copy button element.
 */
export function CopyButton({ getText, label = "Copy report" }: CopyButtonProps): JSX.Element {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(getText());
      setCopied(true);
      window.setTimeout(() => setCopied(false), FEEDBACK_RESET_MS);
    } catch {
      setCopied(false);
    }
  };

  return (
    <button type="button" className={styles.button} onClick={() => void handleCopy()}>
      {copied ? "✓ Copied" : label}
    </button>
  );
}
