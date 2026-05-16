"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Trash2, Globe } from "lucide-react";
import { useChatStore } from "@/store/chatStore";
import { streamQuery } from "@/lib/api";
import { MessageBubble } from "./MessageBubble";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Phân tích cổ phiếu VNM",
  "Định giá HPG có nên mua không?",
  "Phân tích tài chính MWG",
  "FPT đang giao dịch ở mức định giá nào?",
];

export function ChatPanel() {
  const {
    messages,
    locale,
    isStreaming,
    setLocale,
    addUserMessage,
    startAssistantMessage,
    appendToken,
    finalizeMessage,
    setStreaming,
    clearHistory,
    getHistory,
  } = useChatStore();

  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function submit(query: string) {
    if (!query.trim() || isStreaming) return;
    setInput("");

    addUserMessage(query);
    const assistantId = startAssistantMessage();
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamQuery(
        query,
        getHistory(),
        locale,
        (token) => appendToken(assistantId, token),
        (done) => {
          finalizeMessage(
            assistantId,
            done.symbol,
            done.confidence,
            done.valuations,
            done.sources,
            done.warnings
          );
        },
        controller.signal
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        appendToken(assistantId, "\n\n⚠️ Lỗi kết nối tới server. Vui lòng thử lại.");
        finalizeMessage(assistantId, "", 0, [], [], []);
      }
    } finally {
      setStreaming(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600">
            <span className="text-sm font-bold text-white">FA</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-white">FinAdvisor</p>
            <p className="text-xs text-zinc-500">AI Investment Analysis</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Locale toggle */}
          <button
            onClick={() => setLocale(locale === "vi" ? "en" : "vi")}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-800 px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 transition-colors"
          >
            <Globe className="h-3.5 w-3.5" />
            {locale === "vi" ? "🇻🇳 VI" : "🇺🇸 EN"}
          </button>
          <button
            onClick={clearHistory}
            className="rounded-lg bg-zinc-800 p-1.5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700 transition-colors"
            title="Clear chat"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
            <div>
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600/20 border border-indigo-500/20">
                <span className="text-3xl">📊</span>
              </div>
              <h2 className="text-lg font-semibold text-white">
                Phân tích cổ phiếu Việt Nam
              </h2>
              <p className="mt-1 text-sm text-zinc-400">
                Hỏi về bất kỳ cổ phiếu nào trên HOSE, HNX hoặc UPCOM
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 w-full max-w-sm">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="rounded-xl bg-zinc-800/70 border border-zinc-700/50 px-3 py-2.5 text-left text-xs text-zinc-300 hover:bg-zinc-700/70 hover:border-indigo-500/40 transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-zinc-800 px-4 py-3">
        <div className={cn(
          "flex items-end gap-2 rounded-xl bg-zinc-800 border transition-colors px-3 py-2",
          isStreaming ? "border-indigo-500/40" : "border-zinc-700 focus-within:border-indigo-500/60"
        )}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={locale === "vi" ? "Hỏi về cổ phiếu... (e.g. VNM, HPG, FPT)" : "Ask about a stock... (e.g. VNM, HPG, FPT)"}
            rows={1}
            disabled={isStreaming}
            className="flex-1 resize-none bg-transparent text-sm text-white placeholder:text-zinc-500 focus:outline-none disabled:opacity-50 max-h-32"
            style={{ scrollbarWidth: "none" }}
          />
          <button
            onClick={() => submit(input)}
            disabled={!input.trim() || isStreaming}
            className={cn(
              "shrink-0 flex h-8 w-8 items-center justify-center rounded-lg transition-all",
              input.trim() && !isStreaming
                ? "bg-indigo-600 text-white hover:bg-indigo-500"
                : "bg-zinc-700 text-zinc-500 cursor-not-allowed"
            )}
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-zinc-600">
          Không phải tư vấn tài chính cá nhân · Powered by FireAnt + OpenRouter
        </p>
      </div>
    </div>
  );
}
