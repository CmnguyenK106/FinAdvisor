import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(value: number): string {
  return new Intl.NumberFormat("vi-VN").format(Math.round(value));
}

export function confidenceLabel(score: number): string {
  if (score >= 75) return "High";
  if (score >= 50) return "Medium";
  return "Low";
}

export function signalFromContent(content: string): "BUY" | "HOLD" | "SELL" | null {
  const upper = content.toUpperCase();
  if (upper.includes("BUY") || upper.includes("MUA")) return "BUY";
  if (upper.includes("SELL") || upper.includes("BÁN")) return "SELL";
  if (upper.includes("HOLD") || upper.includes("GIỮ")) return "HOLD";
  return null;
}
