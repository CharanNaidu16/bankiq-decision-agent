/**
 * SSE client for the BankIQ investigate endpoint.
 *
 * The browser `EventSource` API cannot send a POST body, so we use `fetch` with
 * a streamed `ReadableStream` and parse the Server-Sent Events frames manually.
 * Frames are separated by a blank line; each frame has `event:` and `data:`
 * lines (the sse-starlette wire format).
 */

import type { AgentProgressEvent, FinalReport } from "../types/investigation";

/** Callbacks invoked as the investigation stream produces events. */
export interface InvestigationStreamHandlers {
  /** Called for each agent progress update. */
  onAgentProgress: (event: AgentProgressEvent) => void;
  /** Called once with the terminal report. */
  onReport: (report: FinalReport) => void;
  /** Called on a stream-level error. */
  onError: (message: string) => void;
  /** Called when the stream completes (success or handled error). */
  onDone: () => void;
}

const INVESTIGATE_ENDPOINT = "/api/investigate";
// SSE frames are separated by a blank line. sse-starlette uses CRLF line
// endings, so the delimiter on the wire is "\r\n\r\n"; tolerate plain "\n\n"
// too. Matching either is essential — a literal "\n\n" split never matches
// "\r\n\r\n" and would silently drop every event.
const SSE_FRAME_DELIMITER = /\r?\n\r?\n/;

/**
 * Start an investigation and dispatch streamed events to the given handlers.
 *
 * @param question - The natural-language banking question to investigate.
 * @param handlers - Callbacks for progress, report, error, and completion.
 * @param signal - Optional AbortSignal to cancel the in-flight request.
 */
export async function startInvestigation(
  question: string,
  handlers: InvestigationStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(INVESTIGATE_ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ question }),
      signal,
    });
  } catch (error) {
    handlers.onError(`Could not reach BankIQ backend: ${String(error)}`);
    handlers.onDone();
    return;
  }

  if (!response.ok || response.body === null) {
    handlers.onError(`Backend returned an error (HTTP ${response.status}).`);
    handlers.onDone();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });

      let match = SSE_FRAME_DELIMITER.exec(buffer);
      while (match !== null) {
        const frame = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        dispatchFrame(frame, handlers);
        match = SSE_FRAME_DELIMITER.exec(buffer);
      }
    }
  } catch (error) {
    if (!(error instanceof DOMException && error.name === "AbortError")) {
      handlers.onError(`Stream interrupted: ${String(error)}`);
    }
  } finally {
    handlers.onDone();
  }
}

/**
 * Parse a single SSE frame and route it to the matching handler.
 *
 * @param frame - The raw text of one SSE frame (without the trailing blank line).
 * @param handlers - Callbacks to dispatch the parsed event to.
 */
function dispatchFrame(frame: string, handlers: InvestigationStreamHandlers): void {
  let eventType = "message";
  const dataLines: string[] = [];

  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }

  const data = dataLines.join("\n");
  if (data.length === 0) {
    return;
  }

  switch (eventType) {
    case "agent_progress":
      handlers.onAgentProgress(JSON.parse(data) as AgentProgressEvent);
      break;
    case "report":
      handlers.onReport(JSON.parse(data) as FinalReport);
      break;
    case "error": {
      const parsed = JSON.parse(data) as { message?: string };
      handlers.onError(parsed.message ?? "Unknown investigation error.");
      break;
    }
    case "done":
      // Stream completion is handled by the reader loop's `finally`.
      break;
    default:
      break;
  }
}
