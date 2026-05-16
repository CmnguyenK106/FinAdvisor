"use client";

import { Bot, User } from "lucide-react";
import { cn, signalFromContent } from "@/lib/utils";
import { SignalBadge } from "./SignalBadge";
import { ConfidenceGauge } from "./ConfidenceGauge";
import { ValuationChart } from "./ValuationChart";
import { WarningsStrip } from "./WarningsStrip";
import type { ChatMessage } from "@/lib/types";

interface Props {
  message: ChatMessage;
}

export function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 w-full", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-indigo-600 text-white"
            : "bg-zinc-700 text-zinc-300"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Bubble */}
      <div className={cn("flex max-w-[80%] flex-col gap-2", isUser && "items-end")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed",
            isUser
              ? "bg-indigo-600 text-white rounded-tr-sm"
              : "bg-zinc-800 text-zinc-100 rounded-tl-sm border border-zinc-700/50"
          )}
        >
          {message.content || (
            <span className="inline-flex gap-1 items-center text-zinc-400">
              <span className="animate-bounce h-1.5 w-1.5 rounded-full bg-zinc-400" style={{ animationDelay: "0ms" }} />
              <span className="animate-bounce h-1.5 w-1.5 rounded-full bg-zinc-400" style={{ animationDelay: "150ms" }} />
              <span className="animate-bounce h-1.5 w-1.5 rounded-full bg-zinc-400" style={{ animationDelay: "300ms" }} />
            </span>
          )}
          {message.streaming && message.content && (
            <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-indigo-400" />
          )}
        </div>

        {/* Signal badge — extracted from answer text */}
        {!isUser && !message.streaming && message.content && (() => {
          const signal = signalFromContent(message.content);
          return signal ? <SignalBadge signal={signal} /> : null;
        })()}

        {/* Post-stream metadata */}
        {!isUser && !message.streaming && message.meta && (
          <div className="w-full space-y-3">
            {message.meta.valuations.length > 0 && (
              <ValuationChart valuations={message.meta.valuations} />
            )}
            <ConfidenceGauge score={message.meta.confidence} />
            <WarningsStrip warnings={message.meta.warnings} />
            {message.meta.sources.length > 0 && (
              <p className="text-xs text-zinc-500">
                Sources: {message.meta.sources.join(", ")}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
