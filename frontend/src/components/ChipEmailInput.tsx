/** A tag-style input that collects multiple email addresses as removable chips. */

import { useState } from "react";

import styles from "../styles/ChipEmailInput.module.css";

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

interface ChipEmailInputProps {
  /** Field label, e.g. "To" or "Cc". */
  label: string;
  /** Current list of committed email addresses. */
  emails: string[];
  /** Called with the updated list whenever a chip is added or removed. */
  onChange: (emails: string[]) => void;
  /** Placeholder shown when no chips are present. */
  placeholder?: string;
  /** Whether the input is disabled (e.g. while sending). */
  disabled?: boolean;
}

/**
 * Render a chip-based email entry field. Type an address and press Enter (or
 * comma) to add it; click ✕ or press Backspace on an empty field to remove one.
 *
 * @param props - Label, the controlled email list, and change handler.
 * @returns The chip input element.
 */
export function ChipEmailInput({
  label,
  emails,
  onChange,
  placeholder,
  disabled,
}: ChipEmailInputProps): JSX.Element {
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);

  const commitDraft = (): void => {
    const candidate = draft.trim().replace(/[,;]+$/, "").trim();
    if (candidate.length === 0) {
      setDraft("");
      return;
    }
    if (!EMAIL_PATTERN.test(candidate)) {
      setInvalid(true);
      return;
    }
    const alreadyPresent = emails.some(
      (existing) => existing.toLowerCase() === candidate.toLowerCase(),
    );
    if (!alreadyPresent) {
      onChange([...emails, candidate]);
    }
    setDraft("");
    setInvalid(false);
  };

  const removeAt = (index: number): void => {
    onChange(emails.filter((_, position) => position !== index));
  };

  return (
    <div className={styles.field}>
      <label className={styles.label}>{label}</label>
      <div className={`${styles.box} ${invalid ? styles.invalidBox : ""}`}>
        {emails.map((email, index) => (
          <span key={email} className={styles.chip}>
            {email}
            <button
              type="button"
              className={styles.chipRemove}
              onClick={() => removeAt(index)}
              aria-label={`Remove ${email}`}
              disabled={disabled}
            >
              ✕
            </button>
          </span>
        ))}
        <input
          className={styles.input}
          type="text"
          value={draft}
          placeholder={emails.length === 0 ? placeholder : ""}
          disabled={disabled}
          onChange={(event) => {
            setDraft(event.target.value);
            setInvalid(false);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === "," || event.key === ";") {
              event.preventDefault();
              commitDraft();
            } else if (event.key === "Backspace" && draft === "" && emails.length > 0) {
              removeAt(emails.length - 1);
            }
          }}
          onBlur={commitDraft}
        />
      </div>
      {invalid && <span className={styles.hint}>Enter a valid email address</span>}
    </div>
  );
}
