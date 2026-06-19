/**
 * React hook encapsulating the investigation lifecycle.
 *
 * Owns the per-agent status rail, the streamed report, error state, and the
 * running flag, and exposes a single `runInvestigation` action. The component
 * tree stays declarative; all SSE plumbing lives here.
 */

import { useCallback, useRef, useState } from "react";

import { startInvestigation } from "../api/investigateClient";
import type {
  AgentName,
  AgentProgressEvent,
  AgentStatus,
  FinalReport,
} from "../types/investigation";

/** Static, ordered definition of the five pipeline agents. */
export const PIPELINE_AGENTS: ReadonlyArray<{ name: AgentName; displayName: string }> = [
  { name: "intent", displayName: "Intent Agent" },
  { name: "data_analyst", displayName: "Data Analyst Agent" },
  { name: "root_cause", displayName: "Root Cause Agent" },
  { name: "impact_forecast", displayName: "Impact Forecast Agent" },
  { name: "executive_report", displayName: "Executive Report Agent" },
];

/** UI-facing status for a single agent in the tracker. */
export interface AgentRunState {
  name: AgentName;
  displayName: string;
  status: AgentStatus;
  message: string;
  elapsedMs: number | null;
}

/** The full state surface returned by the hook. */
export interface UseInvestigationResult {
  isRunning: boolean;
  agentStates: AgentRunState[];
  report: FinalReport | null;
  errorMessage: string | null;
  runInvestigation: (question: string) => void;
}

/**
 * Build the initial agent rail with every agent pending.
 *
 * @returns An array of pending agent run-states in pipeline order.
 */
function createInitialAgentStates(): AgentRunState[] {
  return PIPELINE_AGENTS.map((agent) => ({
    name: agent.name,
    displayName: agent.displayName,
    status: "pending",
    message: "Waiting...",
    elapsedMs: null,
  }));
}

/**
 * Manage an end-to-end investigation run.
 *
 * @returns The current investigation state and a `runInvestigation` trigger.
 */
export function useInvestigation(): UseInvestigationResult {
  const [isRunning, setIsRunning] = useState(false);
  const [agentStates, setAgentStates] = useState<AgentRunState[]>(createInitialAgentStates);
  const [report, setReport] = useState<FinalReport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const applyProgress = useCallback((event: AgentProgressEvent) => {
    setAgentStates((previousStates) =>
      previousStates.map((agentState) =>
        agentState.name === event.agent_name
          ? {
              ...agentState,
              status: event.status,
              message: event.message,
              elapsedMs: event.elapsed_ms,
            }
          : agentState,
      ),
    );
  }, []);

  const runInvestigation = useCallback(
    (question: string) => {
      const trimmedQuestion = question.trim();
      if (trimmedQuestion.length === 0 || isRunning) {
        return;
      }

      abortControllerRef.current?.abort();
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      setIsRunning(true);
      setReport(null);
      setErrorMessage(null);
      setAgentStates(createInitialAgentStates());

      void startInvestigation(
        trimmedQuestion,
        {
          onAgentProgress: applyProgress,
          onReport: (finalReport) => setReport(finalReport),
          onError: (message) => setErrorMessage(message),
          onDone: () => setIsRunning(false),
        },
        abortController.signal,
      );
    },
    [applyProgress, isRunning],
  );

  return { isRunning, agentStates, report, errorMessage, runInvestigation };
}
