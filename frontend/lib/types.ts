// Shared TypeScript types mirroring the backend SSE protocol and REST API.

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ValuationRange {
  low: number;
  high: number;
}

export interface Valuation {
  model: string;
  estimate: number;
  range: ValuationRange;
  confidence: number;
  details: Record<string, unknown>;
  sensitivity: Record<string, unknown>;
}

export interface CAPMResult {
  method: string;
  risk_free_rate: number;
  beta: number;
  market_risk_premium: number;
  cost_of_equity: number;
}

// SSE event types emitted by /api/agent/stream (proxied via gateway)
export type SSETokenEvent = {
  type: "token";
  content: string;
};

export type SSEDoneEvent = {
  type: "done";
  symbol: string;
  confidence: number;
  valuations: Valuation[];
  sources: string[];
  warnings: string[];
};

export type SSEEvent = SSETokenEvent | SSEDoneEvent;

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Populated when role === "assistant" and stream is complete */
  meta?: {
    symbol: string;
    confidence: number;
    valuations: Valuation[];
    sources: string[];
    warnings: string[];
  };
  streaming?: boolean;
}
