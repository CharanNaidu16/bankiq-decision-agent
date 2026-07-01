/** Question textarea with submit and example-query chips. */

import { useState } from "react";

import styles from "../styles/QuestionInput.module.css";

interface QuestionInputProps {
  isRunning: boolean;
  onSubmit: (question: string) => void;
}

/**
 * Pre-written example questions. The first three investigate the distinct
 * planted scenarios (a staffing crisis, a fraud/compliance crisis, and a
 * positive turnaround) across different zones; the last offers a cross-zone
 * overview for users who want the big picture.
 */
const EXAMPLE_QUESTIONS: ReadonlyArray<string> = [
  "Why did our loan approval rate drop 18% in the South zone last quarter?",
  "What caused the Southeast zone's fraud and compliance problems in Q4 2025?",
  "What drove the turnaround and improvement in the Northwest zone during 2025?",
  "Give me a 2025 performance overview across all zones — which improved and which need attention?",
];

/**
 * Render the question input area with example chips and a submit button.
 *
 * @param props - Running state and the submit handler.
 * @returns The input panel element.
 */
export function QuestionInput({ isRunning, onSubmit }: QuestionInputProps): JSX.Element {
  const [question, setQuestion] = useState("");

  const handleSubmit = (): void => {
    if (!isRunning) {
      onSubmit(question);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>): void => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <section className={styles.panel}>
      <label className={styles.label} htmlFor="bankiq-question">
        Ask Enterprise Decision Analysis Agent about a banking KPI anomaly
      </label>
      <textarea
        id="bankiq-question"
        className={styles.textarea}
        placeholder="e.g. Why did our loan approval rate drop 18% in the South zone last quarter?"
        value={question}
        rows={3}
        disabled={isRunning}
        onChange={(event) => setQuestion(event.target.value)}
        onKeyDown={handleKeyDown}
      />

      <div className={styles.chipRow}>
        {EXAMPLE_QUESTIONS.map((example) => (
          <button
            key={example}
            type="button"
            className={styles.chip}
            disabled={isRunning}
            onClick={() => setQuestion(example)}
          >
            {example}
          </button>
        ))}
      </div>

      <div className={styles.actions}>
        <span className={styles.hint}>Press ⌘/Ctrl + Enter to investigate</span>
        <button
          type="button"
          className={styles.submit}
          disabled={isRunning || question.trim().length === 0}
          onClick={handleSubmit}
        >
          {isRunning ? "Investigating…" : "Investigate"}
        </button>
      </div>
    </section>
  );
}
