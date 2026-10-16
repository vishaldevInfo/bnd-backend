"use client";

import Link from "next/link";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Building2, Calculator, Receipt, Wallet } from "lucide-react";
import { MonthlyAmountChart, TopFacilitiesChart } from "@/components/charts";
import { InvoiceTable } from "@/components/invoice-table";
import { Card, CardHeader, DateRangeFilter, EmptyState, ErrorState, PageHeader, Skeleton, TableSkeleton } from "@/components/ui";
import { apiPath, useApi, type DashboardSummary, type PeriodTotals } from "@/lib/api";
import { formatAmount, formatCount, formatDate, percentChange } from "@/lib/format";
import { useUrlParams } from "@/lib/url-state";

export function DashboardView() {
  const url = useUrlParams();
  const start = url.get("start");
  const end = url.get("end");
  const { data, error, loading, reload } = useApi<DashboardSummary>(apiPath("/api/dashboard/summary", { start, end }));

  return (
    <>
      <PageHeader
        title="Invoice Dashboard"
        subtitle={reportingContext(data, start, end)}
        actions={<DateRangeFilter start={start} end={end} onChange={(s, e) => url.set({ start: s, end: e })} />}
      />

      {error ? (
        <Card>
          <ErrorState message={error} onRetry={reload} />
        </Card>
      ) : loading || !data ? (
        <DashboardSkeleton />
      ) : data.current.invoice_count === 0 ? (
        <Card>
          <EmptyState
            title="No invoices in this period"
            message="Try a wider date range, or clear the filter to see all invoices."
            action={
              <button type="button" onClick={() => url.set({ start: null, end: null })} className="text-signal hover:underline">
                Clear date filter
              </button>
            }
          />
        </Card>
      ) : (
        <DashboardContent data={data} start={start} end={end} />
      )}
    </>
  );
}

function reportingContext(data: DashboardSummary | null, start: string, end: string) {
  if (start || end) {
    return `Billed invoices from ${start ? formatDate(start) : "the first invoice"} to ${end ? formatDate(end) : "the latest invoice"}.`;
  }
  if (data?.first_invoice_date) {
    return `All billed invoices, ${formatDate(data.first_invoice_date)} – ${formatDate(data.last_invoice_date)}.`;
  }
  return "Billed invoice totals from the Sage 100 invoice history.";
}

function DashboardContent({ data, start, end }: { data: DashboardSummary; start: string; end: string }) {
  const { current, previous } = data;
  const invoicesHref = apiPath("/invoices", { start, end });

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Total Invoices"
          value={formatCount(current.invoice_count)}
          icon={Receipt}
          tone="teal"
          change={change(current, previous, "invoice_count")}
        />
        <KpiCard
          label="Total Amount"
          value={formatAmount(current.total_amount)}
          icon={Wallet}
          tone="sky"
          change={change(current, previous, "total_amount")}
        />
        <KpiCard
          label="Average Invoice"
          value={formatAmount(current.average_amount)}
          icon={Calculator}
          tone="amber"
          change={change(current, previous, "average_amount")}
        />
        <KpiCard
          label="Active Facilities"
          value={formatCount(current.active_facilities)}
          hint="With at least one invoice in the period"
          icon={Building2}
          tone="violet"
          change={change(current, previous, "active_facilities")}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Monthly Billed Amount" subtitle="Sum of invoice amounts per calendar month" />
          <MonthlyAmountChart data={data.monthly} />
        </Card>
        <Card>
          <CardHeader title="Top Facilities by Amount" subtitle={`Highest ${data.top_facilities.length} in the period`} />
          <TopFacilitiesChart data={data.top_facilities} />
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Recent Invoices"
          subtitle="Latest 10 invoices in the period"
          action={
            <Link href={invoicesHref} className="inline-flex items-center gap-1 text-[13.5px] font-medium text-signal hover:underline">
              View all <ArrowRight size={15} aria-hidden />
            </Link>
          }
        />
        <InvoiceTable rows={data.recent_invoices} />
      </Card>
    </div>
  );
}

// ---------- KPI cards ----------

const TONES = {
  teal: "bg-kpi-teal text-kpi-teal-ink",
  sky: "bg-kpi-sky text-kpi-sky-ink",
  amber: "bg-kpi-amber text-kpi-amber-ink",
  violet: "bg-kpi-violet text-kpi-violet-ink",
};

type Change = { percent: number; days: number } | null;

/** Change vs the previous period; only when the API returned one and it has a non-zero base. */
function change(current: PeriodTotals, previous: PeriodTotals | null, key: keyof PeriodTotals): Change {
  if (!previous || !current.start || !current.end) return null;
  const percent = percentChange(Number(current[key] ?? 0), previous[key] === null ? null : Number(previous[key]));
  if (percent === null) return null;
  const days = Math.round((Date.parse(current.end) - Date.parse(current.start)) / 86_400_000) + 1;
  return { percent, days };
}

function KpiCard({
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

function ChangeBadge({ percent }: { percent: number }) {
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

export function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading dashboard">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="p-5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-4 h-7 w-32" />
            <Skeleton className="mt-3 h-3 w-28" />
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="p-5 xl:col-span-2">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-[240px] w-full" />
        </Card>
        <Card className="p-5">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="mt-4 h-[240px] w-full" />
        </Card>
      </div>
      <Card>
        <TableSkeleton rows={5} />
      </Card>
    </div>
  );
}
