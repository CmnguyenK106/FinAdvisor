"use client";

import { cn } from "@/lib/utils";

type Signal = "BUY" | "HOLD" | "SELL";

const styles: Record<Signal, string> = {
  BUY: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
  HOLD: "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  SELL: "bg-red-500/20 text-red-400 border border-red-500/30",
};

export function SignalBadge({
  signal,
  className,
}: {
  signal: Signal;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold tracking-wide",
        styles[signal],
        className
      )}
    >
      <span className="relative flex h-2 w-2">
        <span
          className={cn(
            "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
            signal === "BUY" ? "bg-emerald-400" : signal === "SELL" ? "bg-red-400" : "bg-amber-400"
          )}
        />
        <span
          className={cn(
            "relative inline-flex rounded-full h-2 w-2",
            signal === "BUY" ? "bg-emerald-500" : signal === "SELL" ? "bg-red-500" : "bg-amber-500"
          )}
        />
      </span>
      {signal}
    </span>
  );
}
