/** Compose-card control that emails the report to multiple To/Cc recipients. */

import { useState } from "react";

import { ChipEmailInput } from "./ChipEmailInput";
import styles from "../styles/EmailReportButton.module.css";

interface EmailReportButtonProps {
  /** Lazily builds the plain-text report body to send. */
  getText: () => string;
  /** Subject line for the email (typically the report title). */
  subject: string;
}

type SendStatus = "idle" | "sending" | "sent" | "error";

const SEND_ENDPOINT = "/api/send-report";
const RESET_MS = 2200;

/**
 * Render an "Email report" button that opens a compose card with To/Cc chip
 * fields and sends the report through the backend's configured SMTP account.
 *
 * @param props - The lazy text provider and the email subject.
 * @returns The email-report control element.
 */
export function EmailReportButton({ getText, subject }: EmailReportButtonProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [to, setTo] = useState<string[]>([]);
  const [cc, setCc] = useState<string[]>([]);
  const [showCc, setShowCc] = useState(false);
  const [status, setStatus] = useState<SendStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const reset = (): void => {
    setOpen(false);
    setTo([]);
    setCc([]);
    setShowCc(false);
    setStatus("idle");
    setErrorMessage("");
  };

  const handleSend = async (): Promise<void> => {
    if (to.length === 0) {
      setErrorMessage("Add at least one recipient.");
      return;
    }
    setStatus("sending");
    setErrorMessage("");
    try {
      const response = await fetch(SEND_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ recipients: to, cc, subject, body: getText() }),
      });
      if (!response.ok) {
        const data = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(data.detail ?? `Request failed (HTTP ${response.status}).`);
      }
      setStatus("sent");
      window.setTimeout(reset, RESET_MS);
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Could not send the email.");
    }
  };

  const totalRecipients = to.length + cc.length;
  const sending = status === "sending";

  return (
    <div className={styles.root}>
      <button
        type="button"
        className={styles.button}
        onClick={() => (open ? reset() : setOpen(true))}
      >
        <svg
          className={styles.icon}
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="m3 7 9 6 9-6" />
        </svg>
        Email report
      </button>

      {open && (
        <div className={styles.card} role="dialog" aria-label="Email report">
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>Email report</span>
            <button type="button" className={styles.close} onClick={reset} aria-label="Close">
              ✕
            </button>
          </div>

          <ChipEmailInput
            label="To"
            emails={to}
            onChange={setTo}
            placeholder="name@email.com"
            disabled={sending}
          />

          {showCc ? (
            <ChipEmailInput
              label="Cc"
              emails={cc}
              onChange={setCc}
              placeholder="name@email.com"
              disabled={sending}
            />
          ) : (
            <button type="button" className={styles.addCc} onClick={() => setShowCc(true)}>
              + Add Cc
            </button>
          )}

          <div className={styles.subjectRow}>
            <span className={styles.subjectLabel}>Subject</span>
            <span className={styles.subjectValue} title={subject}>
              {subject}
            </span>
          </div>

          {status === "error" && <p className={styles.error}>{errorMessage}</p>}

          <div className={styles.footer}>
            <button type="button" className={styles.secondary} onClick={reset}>
              Cancel
            </button>
            <button
              type="button"
              className={styles.primary}
              onClick={() => void handleSend()}
              disabled={sending || to.length === 0}
            >
              {sending
                ? "Sending…"
                : status === "sent"
                  ? "✓ Sent"
                  : totalRecipients > 1
                    ? `Send to ${totalRecipients}`
                    : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
