import { create } from "zustand";
import { nanoid } from "nanoid";
import type { ChatMessage, HistoryMessage, Valuation } from "@/lib/types";

interface ChatStore {
  messages: ChatMessage[];
  locale: "vi" | "en";
  isStreaming: boolean;

  setLocale: (locale: "vi" | "en") => void;
  addUserMessage: (content: string) => string;
  startAssistantMessage: () => string;
  appendToken: (id: string, token: string) => void;
  finalizeMessage: (
    id: string,
    symbol: string,
    confidence: number,
    valuations: Valuation[],
    sources: string[],
    warnings: string[]
  ) => void;
  setStreaming: (v: boolean) => void;
  clearHistory: () => void;

  /** Returns the last N turns as HistoryMessage[] for the API */
  getHistory: (n?: number) => HistoryMessage[];
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  locale: "vi",
  isStreaming: false,

  setLocale: (locale) => set({ locale }),

  addUserMessage: (content) => {
    const id = nanoid();
    set((s) => ({
      messages: [...s.messages, { id, role: "user", content }],
    }));
    return id;
  },

  startAssistantMessage: () => {
    const id = nanoid();
    set((s) => ({
      messages: [
        ...s.messages,
        { id, role: "assistant", content: "", streaming: true },
      ],
    }));
    return id;
  },

  appendToken: (id, token) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      ),
    })),

  finalizeMessage: (id, symbol, confidence, valuations, sources, warnings) =>
    set((s) => ({
      messages: s.messages.map((m) =>
        m.id === id
          ? { ...m, streaming: false, meta: { symbol, confidence, valuations, sources, warnings } }
          : m
      ),
    })),

  setStreaming: (v) => set({ isStreaming: v }),
  clearHistory: () => set({ messages: [] }),

  getHistory: (n = 12) => {
    const msgs = get().messages.slice(-n);
    return msgs.map((m) => ({ role: m.role, content: m.content }));
  },
}));
