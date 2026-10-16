"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { RotateCcw, Search } from "lucide-react";
import { InvoiceTable, type SortKey, type SortOrder } from "@/components/invoice-table";
import {
  buttonStyles,
  Card,
  DateRangeFilter,
  EmptyState,
  ErrorState,
  inputStyles,
  PAGE_SIZES,
  PageHeader,
  Pagination,
  TableSkeleton,
} from "@/components/ui";
import { apiPath, useApi, type Facility, type InvoicePage } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { positiveInt, useUrlParams } from "@/lib/url-state";

const SORT_KEYS: SortKey[] = ["invoice_date", "invoice_no", "member_name", "facility", "amount"];
const SEARCH_DELAY_MS = 350;

export function InvoicesView() {
  const url = useUrlParams();
  const q = url.get("q");
  const start = url.get("start");
  const end = url.get("end");
  const facility = url.get("facility");
  const sort = (SORT_KEYS as string[]).includes(url.get("sort")) ? (url.get("sort") as SortKey) : "invoice_date";
  const order: SortOrder = url.get("order") === "asc" ? "asc" : "desc";
  const page = positiveInt(url.get("page"), 1);
  const pageSize = positiveInt(url.get("page_size"), 25, PAGE_SIZES);

  const { data, error, loading, reload } = useApi<InvoicePage>(
    apiPath("/api/invoices", { q, start, end, facility, sort, order, page, page_size: pageSize }),
  );
  const facilities = useApi<Facility[]>("/api/facilities");
  const hasFilters = Boolean(q || start || end || facility);

  // Every filter change starts again from page 1.
  const setFilters = (changes: Record<string, string | null>) => url.set({ ...changes, page: null });
  const resetFilters = () => setFilters({ q: null, start: null, end: null, facility: null });

  return (
    <>
      <PageHeader title="Invoices" subtitle="Search and filter billed invoices. Select a row to see its line items." />

      <Card>
        <div className="flex flex-col gap-3 border-b border-rule p-4 lg:flex-row lg:flex-wrap lg:items-end">
          <SearchField value={q} onSearch={(value) => setFilters({ q: value })} />
          <label className="flex flex-col gap-1 text-[12px] font-medium text-muted">
            Facility
            <select
              value={facility}
              onChange={(e) => setFilters({ facility: e.target.value })}
              disabled={!facilities.data}
              className={`${inputStyles} w-full lg:w-[240px]`}
            >
              <option value="">{facilities.error ? "Facilities unavailable" : "All facilities"}</option>
              {facilities.data?.map((f) => (
                <option key={f.facility_code} value={f.facility_code}>
                  {f.facility_name}
                </option>
              ))}
            </select>
          </label>
          <DateRangeFilter start={start} end={end} onChange={(s, e) => setFilters({ start: s, end: e })} />
          {hasFilters && (
            <button type="button" onClick={resetFilters} className={`${buttonStyles.secondary} lg:ml-auto`}>
              <RotateCcw size={15} aria-hidden />
              Reset filters
            </button>
          )}
        </div>

        <div className="flex items-center justify-between px-5 py-3 text-[13px] text-ink-soft" aria-live="polite">
          {data ? (
            <span>
              <span className="font-semibold text-ink tabular-nums">{formatCount(data.total)}</span>{" "}
              {data.total === 1 ? "invoice" : "invoices"} {hasFilters ? "match your filters" : "in total"}
            </span>
          ) : (
            <span>{loading ? "Loading invoices…" : " "}</span>
          )}
        </div>

        {error ? (
          <ErrorState message={error} onRetry={reload} />
        ) : loading || !data ? (
          <TableSkeleton rows={10} />
        ) : data.items.length === 0 ? (
          <EmptyState
            title={data.total === 0 ? "No invoices found" : "This page is empty"}
            message={hasFilters ? "No invoice matches these filters. Try a different search or date range." : undefined}
            action={
              hasFilters ? (
                <button type="button" onClick={resetFilters} className={buttonStyles.secondary}>
                  Reset filters
                </button>
              ) : undefined
            }
          />
        ) : (
          <>
            <InvoiceTable
              rows={data.items}
              sorting={{ sort, order, onSort: (s, o) => url.set({ sort: s, order: o, page: null }) }}
            />
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPageChange={(p) => url.set({ page: p === 1 ? null : p })}
              onPageSizeChange={(size) => url.set({ page_size: size === 25 ? null : size, page: null })}
            />
          </>
        )}
      </Card>
    </>
  );
}

/** Search box that updates the URL shortly after typing stops. */
function SearchField({ value, onSearch }: { value: string; onSearch: (value: string) => void }) {
  const [draft, setDraft] = useState({ text: value, source: value });
  if (draft.source !== value) setDraft({ text: value, source: value }); // follow outside changes (reset, top bar)

  const search = useEffectEvent((text: string) => onSearch(text));
  useEffect(() => {
    const text = draft.text.trim();
    if (text === value) return;
    const timer = setTimeout(() => search(text), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [draft.text, value]);

  return (
    <label className="flex flex-1 flex-col gap-1 text-[12px] font-medium text-muted lg:min-w-[260px]">
      Search
      <span className="relative">
        <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
        <input
          type="search"
          value={draft.text}
          maxLength={100}
          onChange={(e) => setDraft({ ...draft, text: e.target.value })}
          placeholder="Invoice no, member no or member name"
          className={`${inputStyles} w-full pl-9`}
        />
      </span>
    </label>
  );
}
