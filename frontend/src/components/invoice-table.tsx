"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { Amount } from "@/components/ui";
import { invoiceHref, type InvoiceRow } from "@/lib/api";
import { formatDate } from "@/lib/format";

export type SortKey = "invoice_date" | "invoice_no" | "member_name" | "facility" | "amount";
export type SortOrder = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; align?: "right" }[] = [
  { key: "invoice_no", label: "Invoice" },
  { key: "member_name", label: "Member" },
  { key: "facility", label: "Facility" },
  { key: "invoice_date", label: "Date" },
  { key: "amount", label: "Amount", align: "right" },
];

type Sorting = { sort: SortKey; order: SortOrder; onSort: (sort: SortKey, order: SortOrder) => void };

/**
 * One row per invoice. The whole row opens the invoice; the invoice number is
 * also a real link so keyboard and screen-reader users can reach it.
 * Wide tables scroll horizontally on small screens instead of squashing.
 */
export function InvoiceTable({ rows, sorting }: { rows: InvoiceRow[]; sorting?: Sorting }) {
  const router = useRouter();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-[13.5px]">
        <thead>
          <tr className="border-y border-rule bg-paper/60 text-left text-[11.5px] font-semibold tracking-[0.06em] text-muted uppercase">
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={
                  sorting?.sort === column.key ? (sorting.order === "asc" ? "ascending" : "descending") : undefined
                }
                className={`px-5 py-2.5 font-semibold ${column.align === "right" ? "text-right" : ""}`}
              >
                {sorting ? <SortButton column={column} sorting={sorting} /> : column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule">
          {rows.map((row) => (
            <tr
              key={`${row.invoice_no}-${row.header_seq}`}
              onClick={() => router.push(invoiceHref(row))}
              className="cursor-pointer hover:bg-row-hover"
            >
              <td className="px-5 py-3 font-medium whitespace-nowrap">
                <Link
                  href={invoiceHref(row)}
                  onClick={(e) => e.stopPropagation()}
                  className="text-signal tabular-nums hover:underline"
                >
                  #{row.invoice_no}
                </Link>
              </td>
              <td className="px-5 py-3">
                <span className="block">{row.member_name || "—"}</span>
                <span className="text-[12px] text-muted tabular-nums">{row.member_no}</span>
              </td>
              <td className="max-w-[260px] px-5 py-3">
                <span className={`block truncate ${row.facility_known ? "" : "text-muted italic"}`} title={row.facility_name}>
                  {row.facility_name}
                </span>
              </td>
              <td className="px-5 py-3 whitespace-nowrap text-ink-soft tabular-nums">{formatDate(row.invoice_date)}</td>
              <td className="px-5 py-3 text-right font-medium whitespace-nowrap">
                <Amount value={row.amount} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortButton({ column, sorting }: { column: (typeof COLUMNS)[number]; sorting: Sorting }) {
  const active = sorting.sort === column.key;
  const Icon = !active ? ArrowUpDown : sorting.order === "asc" ? ArrowUp : ArrowDown;
  // First click on a new column: dates and amounts start high-to-low, text A-Z.
  const firstOrder: SortOrder = column.key === "invoice_date" || column.key === "amount" ? "desc" : "asc";
  const nextOrder: SortOrder = active ? (sorting.order === "asc" ? "desc" : "asc") : firstOrder;

  return (
    <button
      type="button"
      onClick={() => sorting.onSort(column.key, nextOrder)}
      className={`inline-flex items-center gap-1 uppercase hover:text-ink ${active ? "text-ink" : ""} ${
        column.align === "right" ? "flex-row-reverse" : ""
      }`}
    >
      {column.label}
      <Icon size={13} aria-hidden className={active ? "" : "opacity-50"} />
    </button>
  );
}
