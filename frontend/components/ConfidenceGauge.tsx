"use client";

import { cn, confidenceLabel } from "@/lib/utils";

interface Props {
  score: number;
  className?: string;
}

const COLORS = {
  high: "from-emerald-500 to-green-400",
  medium: "from-amber-500 to-yellow-400",
  low: "from-red-500 to-rose-400",
};

export function ConfidenceGauge({ score, className }: Props) {
  const label = confidenceLabel(score);
  const color =
    score >= 75 ? COLORS.high : score >= 50 ? COLORS.medium : COLORS.low;

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex items-center justify-between text-xs text-zinc-400">
        <span>Confidence</span>
        <span className="font-semibold text-white">
          {score}% — {label}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-zinc-700 overflow-hidden">
        <div
          className={cn("h-full rounded-full bg-gradient-to-r transition-all duration-700", color)}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}
