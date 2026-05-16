"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ErrorBar,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { formatPrice } from "@/lib/utils";
import type { Valuation } from "@/lib/types";

const MODEL_COLORS: Record<string, string> = {
  multiples: "#6366f1",
  dcf: "#0ea5e9",
  ddm: "#10b981",
  book_value: "#f59e0b",
  graham: "#ec4899",
};

interface Props {
  valuations: Valuation[];
}

export function ValuationChart({ valuations }: Props) {
  if (!valuations.length) return null;

  const data = valuations.map((v) => ({
    name: v.model.replace("_", " ").toUpperCase(),
    estimate: Math.round(v.estimate),
    errorY: [
      Math.round(v.estimate - v.range.low),
      Math.round(v.range.high - v.estimate),
    ] as [number, number],
    confidence: v.confidence,
    model: v.model,
  }));

  return (
    <div className="rounded-xl bg-zinc-800/50 border border-zinc-700/50 p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-400">
        Fair Value Estimates (VND)
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="name"
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "#18181b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              color: "#f4f4f5",
            }}
            formatter={(value, name) => {
              if (name === "estimate") return [formatPrice(Number(value)) + " VND", "Estimate"];
              return [value, name];
            }}
          />
          <Bar dataKey="estimate" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.model}
                fill={MODEL_COLORS[entry.model] ?? "#6366f1"}
                fillOpacity={0.85}
              />
            ))}
            <ErrorBar
              dataKey="errorY"
              width={4}
              strokeWidth={2}
              stroke="#71717a"
              direction="y"
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Confidence table */}
      <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-3">
        {valuations.map((v) => (
          <div
            key={v.model}
            className="flex items-center justify-between rounded-lg bg-zinc-900/60 px-2.5 py-1.5 text-xs"
          >
            <span
              className="font-medium capitalize"
              style={{ color: MODEL_COLORS[v.model] ?? "#a1a1aa" }}
            >
              {v.model.replace("_", " ")}
            </span>
            <span className="text-zinc-300">{v.confidence}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
