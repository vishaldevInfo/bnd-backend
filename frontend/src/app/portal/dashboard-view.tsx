"use client";

import Link from "next/link";
import { ArrowRight, Calculator, CalendarClock, Receipt, Wallet } from "lucide-react";
import { MonthlyAmountChart } from "@/components/charts";
import { change, KpiCard } from "@/components/kpi-card";
import { InvoiceTable } from "@/components/invoice-table";
import { Card, CardHeader, DateRangeFilter, EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui";
import { apiPath, useApi, type InvoicePage, type PortalSummary } from "@/lib/api";
import { formatAmount, formatCount, formatDate } from "@/lib/format";
import { useUrlParams } from "@/lib/url-state";

const RECENT_COUNT = 5;

export function DashboardView() {
  const url = useUrlParams();
  const start = url.get("start");
  const end = url.get("end");
  const summary = useApi<PortalSummary>(apiPath("/api/portal/summary", { start, end }));
  const recent = useApi<InvoicePage>(apiPath("/api/invoices", { start, end, sort: "invoice_date", order: "desc", page_size: RECENT_COUNT }));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle={subtitle(summary.data, start, end)}
        actions={<DateRangeFilter start={start} end={end} onChange={(s, e) => url.set({ start: s, end: e })} />}
      />

      {summary.error ? (
        <Card>
          <ErrorState message={summary.error} onRetry={summary.reload} />
        </Card>
      ) : !summary.data ? (
        <DashboardSkeleton />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              label="Invoices"
              value={formatCount(summary.data.current.invoice_count)}
              icon={Receipt}
              tone="teal"
              change={change(summary.data.current, summary.data.previous, "invoice_count")}
            />
            <KpiCard
              label="Total Billed"
              value={formatAmount(summary.data.current.total_amount)}
              icon={Wallet}
              tone="sky"
              change={change(summary.data.current, summary.data.previous, "total_amount")}
            />
            <KpiCard
              label="Average Invoice"
              value={formatAmount(summary.data.current.average_amount)}
              icon={Calculator}
              tone="amber"
              change={change(summary.data.current, summary.data.previous, "average_amount")}
            />
            <KpiCard
              label="Latest Invoice"
              value={formatDate(summary.data.last_invoice_date)}
              hint={summary.data.first_invoice_date ? `First invoice ${formatDate(summary.data.first_invoice_date)}` : "No invoices yet"}
              icon={CalendarClock}
              tone="violet"
              change={null}
            />
          </div>

          <Card>
            <CardHeader title="Monthly Billed Amount" subtitle="Sum of your invoice amounts per calendar month" />
            {summary.data.current.invoice_count === 0 ? (
              <EmptyState title="No invoices in this period" message="Try a wider date range or clear the filter." />
            ) : (
              <MonthlyAmountChart data={summary.data.monthly} />
            )}
          </Card>

          <Card>
            <CardHeader
              title="Recent Invoices"
              subtitle={`Latest ${RECENT_COUNT} in the period`}
              action={
                <Link href={apiPath("/portal/invoices", { start, end })} className="inline-flex items-center gap-1 text-[13.5px] font-medium text-signal hover:underline">
                  View all <ArrowRight size={15} aria-hidden />
                </Link>
              }
            />
            {recent.error ? (
              <ErrorState message={recent.error} onRetry={recent.reload} />
            ) : !recent.data ? (
              <div className="h-40" role="status" aria-label="Loading recent invoices" />
            ) : recent.data.items.length === 0 ? (
              <EmptyState title="No invoices in this period" />
            ) : (
              <InvoiceTable customer rows={recent.data.items} />
            )}
          </Card>
        </>
      )}
    </div>
  );
}

function subtitle(data: PortalSummary | null, start: string, end: string) {
  if (start || end) {
    return `Billed invoices from ${start ? formatDate(start) : "your first invoice"} to ${end ? formatDate(end) : "your latest invoice"}.`;
  }
  if (data?.first_invoice_date) {
    return `Your billed invoices, ${formatDate(data.first_invoice_date)} – ${formatDate(data.last_invoice_date)}.`;
  }
  return "Your billed invoices.";
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading your dashboard">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} className="p-5">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="mt-4 h-7 w-32" />
            <Skeleton className="mt-3 h-3 w-28" />
          </Card>
        ))}
      </div>
      <Card className="p-5">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-4 h-[240px] w-full" />
      </Card>
    </div>
  );
}
