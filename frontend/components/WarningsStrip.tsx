"use client";

import { AlertTriangle } from "lucide-react";

export function WarningsStrip({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <div className="mt-3 flex flex-col gap-1.5">
      {warnings.map((w, i) => (
        <div
          key={i}
          className="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-xs text-amber-300"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>{w}</span>
        </div>
      ))}
    </div>
  );
}
