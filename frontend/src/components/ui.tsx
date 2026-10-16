"use client";

// Small building blocks shared by every page. Kept in one file on purpose:
// each piece is short, and together they define the app's visual language.
import { useState } from "react";
import { AlertTriangle, CalendarRange, ChevronLeft, ChevronRight, Inbox, RotateCw, X } from "lucide-react";
import { formatAmount, isNegative } from "@/lib/format";

// ---------- Layout ----------

export function Card({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return <section className={`rounded-lg border border-rule bg-surface ${className}`}>{children}</section>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
      <div>
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 className="text-[22px] font-semibold tracking-[-0.02em] sm:text-[24px]">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-end gap-2">{actions}</div>}
    </div>
  );
}

// ---------- Buttons ----------

export const buttonStyles = {
  primary:
    "inline-flex h-9 items-center justify-center gap-2 rounded-md bg-signal px-3.5 text-[13.5px] font-medium text-white hover:bg-signal-lift disabled:pointer-events-none disabled:opacity-50",
  secondary:
    "inline-flex h-9 items-center justify-center gap-2 rounded-md border border-rule bg-surface px-3 text-[13.5px] font-medium text-ink-soft hover:border-rule-firm hover:text-ink disabled:pointer-events-none disabled:opacity-50",
  icon: "inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-soft hover:bg-paper hover:text-ink",
};

export const inputStyles =
  "h-9 rounded-md border border-rule-firm bg-surface px-3 text-[13.5px] text-ink outline-none placeholder:text-muted focus:border-signal focus:ring-2 focus:ring-signal/20";

// ---------- States ----------

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-md bg-rule/70 ${className}`} />;
}

export function TableSkeleton({ rows = 8, columns = 5 }: { rows?: number; columns?: number }) {
  return (
    <div role="status" aria-label="Loading" className="divide-y divide-rule">
      {Array.from({ length: rows }, (_, row) => (
        <div key={row} className="flex gap-6 px-5 py-3.5">
          {Array.from({ length: columns }, (_, col) => (
            <Skeleton key={col} className={`h-4 ${col === 0 ? "w-20" : "flex-1"}`} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-paper text-muted">
        <Inbox size={20} aria-hidden />
      </span>
      <p className="font-medium">{title}</p>
      {message && <p className="mt-1 max-w-sm text-[13px] text-muted">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-12 text-center">
      <span className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-negative-tint text-negative">
        <AlertTriangle size={20} aria-hidden />
      </span>
      <p className="font-medium">Could not load this data</p>
      <p className="mt-1 max-w-sm text-[13px] text-muted">{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className={`${buttonStyles.secondary} mt-4`}>
          <RotateCw size={15} aria-hidden />
          Try again
        </button>
      )}
    </div>
  );
}

// ---------- Values ----------

/** Money with tabular figures; negative amounts (credits/adjustments) in red. */
export function Amount({ value, className = "" }: { value: string | null | undefined; className?: string }) {
  const negative = value !== null && value !== undefined && isNegative(value);
  return <span className={`tabular-nums ${negative ? "text-negative" : ""} ${className}`}>{formatAmount(value)}</span>;
}

// ---------- Filters ----------

/**
 * Start/end date inputs applied together, so a half-edited range never triggers
 * a request. Dates are YYYY-MM-DD strings; empty means "no limit".
 */
export function DateRangeFilter({
  start,
  end,
  onChange,
}: {
  start: string;
  end: string;
  onChange: (start: string, end: string) => void;
}) {
  const [draft, setDraft] = useState({ start, end, sourceStart: start, sourceEnd: end });
  // Follow outside changes (e.g. "Reset filters") without an effect.
  if (draft.sourceStart !== start || draft.sourceEnd !== end) {
    setDraft({ start, end, sourceStart: start, sourceEnd: end });
  }
  const invalid = Boolean(draft.start && draft.end && draft.start > draft.end);
  const changed = draft.start !== start || draft.end !== end;

  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (!invalid) onChange(draft.start, draft.end);
      }}
    >
      <label className="flex flex-col gap-1 text-[12px] font-medium text-muted">
        From
        <input
          type="date"
          value={draft.start}
          onChange={(e) => setDraft({ ...draft, start: e.target.value })}
          aria-invalid={invalid}
          className={`${inputStyles} w-[150px]`}
        />
      </label>
      <label className="flex flex-col gap-1 text-[12px] font-medium text-muted">
        To
        <input
          type="date"
          value={draft.end}
          onChange={(e) => setDraft({ ...draft, end: e.target.value })}
          aria-invalid={invalid}
          className={`${inputStyles} w-[150px]`}
        />
      </label>
      <button type="submit" disabled={invalid || !changed} className={buttonStyles.secondary}>
        <CalendarRange size={15} aria-hidden />
        Apply
      </button>
      {(start || end) && (
        <button type="button" onClick={() => onChange("", "")} className={buttonStyles.secondary}>
          <X size={15} aria-hidden />
          Clear
        </button>
      )}
      {invalid && (
        <p role="alert" className="w-full text-[12.5px] text-negative">
          The start date must be on or before the end date.
        </p>
      )}
    </form>
  );
}

export const PAGE_SIZES = [25, 50, 100];

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule px-5 py-3 text-[13px] text-ink-soft">
      <p className="tabular-nums">
        {first.toLocaleString("en-US")}–{last.toLocaleString("en-US")} of{" "}
        <span className="font-semibold text-ink">{total.toLocaleString("en-US")}</span>
      </p>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-2">
          Rows per page
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className={`${inputStyles} h-8 px-2`}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <span className="tabular-nums">
          Page {page.toLocaleString("en-US")} of {pageCount.toLocaleString("en-US")}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
            className={`${buttonStyles.secondary} h-8 w-8 px-0`}
          >
            <ChevronLeft size={16} aria-hidden />
          </button>
          <button
            type="button"
            aria-label="Next page"
            disabled={page >= pageCount}
            onClick={() => onPageChange(page + 1)}
            className={`${buttonStyles.secondary} h-8 w-8 px-0`}
          >
            <ChevronRight size={16} aria-hidden />
          </button>
        </div>
      </div>
    </div>
  );
}
