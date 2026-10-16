"use client";

import { Download } from "lucide-react";
import { InvoiceTable } from "@/components/invoice-table";
import {
  buttonStyles,
  Card,
  CardHeader,
  DateRangeFilter,
  EmptyState,
  ErrorState,
  PAGE_SIZES,
  PageHeader,
  Pagination,
  Skeleton,
  TableSkeleton,
} from "@/components/ui";
import { apiPath, useApi, type InvoiceReport } from "@/lib/api";
import { formatAmount, formatCount, formatDate } from "@/lib/format";
import { positiveInt, useUrlParams } from "@/lib/url-state";

export function ReportsView() {
  const url = useUrlParams();
  const start = url.get("start");
  const end = url.get("end");
  const page = positiveInt(url.get("page"), 1);
  const pageSize = positiveInt(url.get("page_size"), 50, PAGE_SIZES);

  const { data, error, loading, reload } = useApi<InvoiceReport>(
    apiPath("/api/reports/invoices", { start, end, page, page_size: pageSize }),
  );
  // Same date filters as the on-screen report, so the CSV matches it exactly.
  const exportHref = apiPath("/api/reports/invoices/export", { start, end });
  const period = `${start ? formatDate(start) : "First invoice"} – ${end ? formatDate(end) : "latest invoice"}`;

  return (
    <>
      <PageHeader
        title="Invoice Report"
        subtitle="One row per invoice, with the count and total for the period. Download it as CSV."
        actions={
          <DateRangeFilter start={start} end={end} onChange={(s, e) => url.set({ start: s, end: e, page: null })} />
        }
      />

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryTile label="Period" value={period} />
        <SummaryTile label="Invoices" value={data ? formatCount(data.invoice_count) : error ? "—" : null} />
        <SummaryTile label="Total amount" value={data ? formatAmount(data.total_amount) : error ? "—" : null} />
      </div>

      <Card>
        <CardHeader
          title="Invoices"
          subtitle="Sorted by invoice date, oldest first"
          action={
            data && data.invoice_count > 0 ? (
              <a href={exportHref} download className={buttonStyles.primary}>
                <Download size={15} aria-hidden />
                Download CSV
              </a>
            ) : (
              <button type="button" disabled className={buttonStyles.primary}>
                <Download size={15} aria-hidden />
                Download CSV
              </button>
            )
          }
        />
        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : loading || !data ? (
          <TableSkeleton rows={10} />
        ) : data.invoice_count === 0 ? (
          <EmptyState title="No invoices in this period" message="Choose a different date range to build the report." />
        ) : (
          <>
            <InvoiceTable rows={data.rows} />
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.invoice_count}
              onPageChange={(p) => url.set({ page: p === 1 ? null : p })}
              onPageSizeChange={(size) => url.set({ page_size: size === 50 ? null : size, page: null })}
            />
          </>
        )}
      </Card>
    </>
  );
}

function SummaryTile({ label, value }: { label: string; value: string | null }) {
  return (
    <Card className="p-5">
      <p className="text-[13px] font-medium text-ink-soft">{label}</p>
      {value === null ? (
        <Skeleton className="mt-2 h-7 w-32" />
      ) : (
        <p className="mt-1 text-[20px] font-semibold tracking-[-0.01em] tabular-nums">{value}</p>
      )}
    </Card>
  );
}
