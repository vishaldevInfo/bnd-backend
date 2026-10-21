"use client";

import { InvoiceTable, type SortKey, type SortOrder } from "@/components/invoice-table";
import { SearchField } from "@/components/search-field";
import { buttonStyles, Card, CardHeader, DateRangeFilter, EmptyState, ErrorState, PAGE_SIZES, PageHeader, Pagination, TableSkeleton } from "@/components/ui";
import { apiPath, useApi, type InvoicePage } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { positiveInt, useUrlParams } from "@/lib/url-state";

// Customers may not sort by member name: that column is hidden for them.
const SORT_KEYS: SortKey[] = ["invoice_date", "invoice_no", "facility", "amount"];

export function InvoicesView() {
  const url = useUrlParams();
  const q = url.get("q");
  const start = url.get("start");
  const end = url.get("end");
  const sort = (SORT_KEYS as string[]).includes(url.get("sort")) ? (url.get("sort") as SortKey) : "invoice_date";
  const order: SortOrder = url.get("order") === "asc" ? "asc" : "desc";
  const page = positiveInt(url.get("page"), 1);
  const pageSize = positiveInt(url.get("page_size"), 25, PAGE_SIZES);

  const invoices = useApi<InvoicePage>(apiPath("/api/invoices", { q, start, end, sort, order, page, page_size: pageSize }));
  const hasFilters = Boolean(q || start || end);

  // Every filter change starts again from page 1.
  const setFilters = (changes: Record<string, string | null>) => url.set({ ...changes, page: null });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Invoices"
        subtitle="Your billed invoices. Filter by date or invoice number."
        actions={<DateRangeFilter start={start} end={end} onChange={(s, e) => setFilters({ start: s, end: e })} />}
      />

      <Card>
        <CardHeader title="All invoices" subtitle={invoices.data ? `${formatCount(invoices.data.total)} matching` : undefined} />
        <div className="flex flex-col gap-3 border-b border-rule p-4 lg:flex-row lg:flex-wrap lg:items-end">
          <SearchField value={q} onSearch={(value) => setFilters({ q: value })} placeholder="Invoice number" />
          {hasFilters && (
            <button type="button" onClick={() => setFilters({ q: null, start: null, end: null })} className={buttonStyles.secondary}>
              Clear filters
            </button>
          )}
        </div>

        {invoices.error ? (
          <ErrorState message={invoices.error} onRetry={invoices.reload} />
        ) : !invoices.data ? (
          <TableSkeleton rows={10} columns={4} />
        ) : invoices.data.items.length === 0 ? (
          <EmptyState
            title={hasFilters ? "No invoices match these filters" : "No invoices yet"}
            message={hasFilters ? "Try a different search or date range." : "Invoices for your account will appear here."}
          />
        ) : (
          <>
            <InvoiceTable
              customer
              rows={invoices.data.items}
              sorting={{ sort, order, onSort: (s, o) => url.set({ sort: s, order: o, page: null }) }}
            />
            <Pagination
              page={page}
              pageSize={pageSize}
              total={invoices.data.total}
              onPageChange={(next) => url.set({ page: next })}
              onPageSizeChange={(size) => url.set({ page_size: size, page: null })}
            />
          </>
        )}
      </Card>
    </div>
  );
}
