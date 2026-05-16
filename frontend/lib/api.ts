// SSE streaming client + REST helpers for the FinAdvisor gateway.

import type { SSEEvent, HistoryMessage } from "./types";

const GATEWAY = process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://localhost:8081";

/**
 * Streams an agent answer via SSE.
 * Calls `onToken` for each text chunk and `onDone` with the final metadata.
 */
export async function streamQuery(
  query: string,
  history: HistoryMessage[],
  locale: string,
  onToken: (token: string) => void,
  onDone: (event: SSEEvent & { type: "done" }) => void,
  signal?: AbortSignal
): Promise<void> {
  const res = await fetch(`${GATEWAY}/api/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, history, locale }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Gateway error: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;
      try {
        const evt = JSON.parse(raw) as SSEEvent;
        if (evt.type === "token") onToken(evt.content);
        else if (evt.type === "done") onDone(evt);
      } catch {
        // malformed chunk — skip
      }
    }
  }
}
