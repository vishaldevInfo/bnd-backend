"use client";

import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui";
import type { PeriodTotals } from "@/lib/api";
import { percentChange } from "@/lib/format";

export const TONES = {
  teal: "bg-kpi-teal text-kpi-teal-ink",
  sky: "bg-kpi-sky text-kpi-sky-ink",
  amber: "bg-kpi-amber text-kpi-amber-ink",
  violet: "bg-kpi-violet text-kpi-violet-ink",
};

export type Change = { percent: number; days: number } | null;

/** Change vs the previous period; only when the API returned one and it has a non-zero base. */
export function change(current: PeriodTotals, previous: PeriodTotals | null, key: keyof PeriodTotals): Change {
  if (!previous || !current.start || !current.end) return null;
  const percent = percentChange(Number(current[key] ?? 0), previous[key] === null ? null : Number(previous[key]));
  if (percent === null) return null;
  const days = Math.round((Date.parse(current.end) - Date.parse(current.start)) / 86_400_000) + 1;
  return { percent, days };
}

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone,
  change,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: React.ComponentType<{ size?: number; "aria-hidden"?: boolean }>;
  tone: keyof typeof TONES;
  change: Change;
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[13px] font-medium text-ink-soft">{label}</p>
        <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${TONES[tone]}`}>
          <Icon size={18} aria-hidden />
        </span>
      </div>
      <p className="mt-2 text-[26px] leading-tight font-semibold tracking-[-0.02em] tabular-nums">{value}</p>
      <div className="mt-2 flex min-h-5 flex-wrap items-center gap-2 text-[12px] text-muted">
        {change && <ChangeBadge percent={change.percent} />}
        {change ? <span>vs previous {change.days} days</span> : hint && <span>{hint}</span>}
      </div>
    </Card>
  );
}

export function ChangeBadge({ percent }: { percent: number }) {
  const up = percent >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 font-semibold tabular-nums ${
        up ? "bg-positive-tint text-positive" : "bg-negative-tint text-negative"
      }`}
    >
      <Icon size={13} aria-hidden />
      <span className="sr-only">{up ? "Up" : "Down"}</span>
      {Math.abs(percent).toFixed(1)}%
    </span>
  );
}
