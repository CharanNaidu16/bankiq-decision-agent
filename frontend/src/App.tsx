/** Top-level application shell wiring the input, progress rail, and report. */

import { AgentProgressTracker } from "./components/AgentProgressTracker";
import { ExecutiveReportView } from "./components/ExecutiveReportView";
import { QuestionInput } from "./components/QuestionInput";
import { useInvestigation } from "./hooks/useInvestigation";
import styles from "./styles/App.module.css";

/**
 * Render the Enterprise Decision Analysis Agent single-page application.
 *
 * @returns The application root element.
 */
export default function App(): JSX.Element {
  const { isRunning, agentStates, report, errorMessage, runInvestigation } = useInvestigation();
  const hasStarted = isRunning || report !== null || errorMessage !== null;

  return (
    <div className={styles.app}>
      <header className={styles.masthead}>
        <div className={styles.brand}>
          <span className={styles.logo}>◆</span>
          <div>
            <h1 className={styles.productName}>Enterprise Decision Analysis Agent</h1>
            <p className={styles.tagline}>Enterprise Decision Intelligence Agent</p>
          </div>
        </div>
        <p className={styles.subtitle}>
          Ask a question. Five autonomous agents investigate seven datasets, build a causal
          evidence chain, and deliver a board-ready report.
        </p>
      </header>

      <main className={styles.main}>
        <QuestionInput isRunning={isRunning} onSubmit={runInvestigation} />

        {errorMessage && (
          <div className={styles.error} role="alert">
            {errorMessage}
          </div>
        )}

        {hasStarted && (
          <div className={styles.workspace}>
            <aside className={styles.sidebar}>
              <AgentProgressTracker agentStates={agentStates} />
            </aside>
            <div className={styles.content}>
              {report ? (
                <ExecutiveReportView finalReport={report} />
              ) : (
                <div className={styles.placeholder}>
                  <div className={styles.pulse} />
                  <p>Enterprise Decision Analysis Agent is investigating your question…</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        Enterprise Decision Analysis Agent runs on Groq · synthetic data · for demonstration purposes
      </footer>
    </div>
  );
}
