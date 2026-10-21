"use client";

import Link from "next/link";
import { ArrowRight, Building2, Calculator, Receipt, Wallet } from "lucide-react";
import { MonthlyAmountChart, TopFacilitiesChart } from "@/components/charts";
import { InvoiceTable } from "@/components/invoice-table";
import { change, KpiCard } from "@/components/kpi-card";
import { Card, CardHeader, DateRangeFilter, EmptyState, ErrorState, PageHeader, Skeleton, TableSkeleton } from "@/components/ui";
import { apiPath, useApi, type DashboardSummary } from "@/lib/api";
import { formatAmount, formatCount, formatDate } from "@/lib/format";
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
