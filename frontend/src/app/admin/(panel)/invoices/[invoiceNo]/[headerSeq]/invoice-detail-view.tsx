"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import { Amount, Card, CardHeader, EmptyState, ErrorState, Skeleton, TableSkeleton } from "@/components/ui";
import { useApi, type InvoiceDetail } from "@/lib/api";
import { formatDate } from "@/lib/format";

export function InvoiceDetailView() {
  const params = useParams<{ invoiceNo: string; headerSeq: string }>();
  const path = `/api/invoices/${encodeURIComponent(params.invoiceNo)}/${encodeURIComponent(params.headerSeq)}`;
  const { data, error, loading, reload } = useApi<InvoiceDetail>(path);
  const notFound = error === "Invoice not found.";

  return (
    <>
      <Link href="/admin/invoices" className="mb-4 inline-flex items-center gap-1.5 text-[13.5px] font-medium text-ink-soft hover:text-ink">
        <ArrowLeft size={16} aria-hidden />
        Back to invoices
      </Link>

      {notFound ? (
        <Card>
          <EmptyState
            title="Invoice not found"
            message={`There is no invoice ${decodeURIComponent(params.invoiceNo)} in the invoice history.`}
          />
        </Card>
      ) : error ? (
        <Card>
          <ErrorState message={error} onRetry={reload} />
        </Card>
      ) : loading || !data ? (
        <InvoiceDetailSkeleton />
      ) : (
        <InvoiceContent invoice={data} />
      )}
    </>
  );
}

function InvoiceContent({ invoice }: { invoice: InvoiceDetail }) {
  const linesMatch = Number(invoice.lines_total) === Number(invoice.amount);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-[22px] font-semibold tracking-[-0.02em] tabular-nums sm:text-[24px]">Invoice #{invoice.invoice_no}</h1>
          <p className="mt-1 text-muted">
            Issued {formatDate(invoice.invoice_date)} to {invoice.member_name || "an unnamed member"}
          </p>
        </div>
        <div className="sm:text-right">
          <p className="text-[12px] font-medium text-muted">Invoice amount</p>
          <Amount value={invoice.amount} className="text-[26px] font-semibold tracking-[-0.02em]" />
        </div>
      </div>

      <Card className="p-5">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Member">
            {invoice.member_name || <NotRecorded />}
            <span className="block text-[12.5px] text-muted tabular-nums">{invoice.member_no}</span>
          </Field>
          <Field label="Facility">
            <span className={invoice.facility_known ? "" : "text-muted italic"}>{invoice.facility_name}</span>
            <span className="block text-[12.5px] text-muted">Code {invoice.facility_code}</span>
          </Field>
          <Field label="Invoice date">{formatDate(invoice.invoice_date)}</Field>
          <Field label="Due date">{invoice.due_date ? formatDate(invoice.due_date) : <NotRecorded />}</Field>
          <Field label="Taxable amount">
            <Amount value={invoice.taxable_amount} />
          </Field>
          <Field label="Non-taxable amount">
            <Amount value={invoice.non_taxable_amount} />
          </Field>
          <Field label="Terms code">{invoice.terms_code ?? <NotRecorded />}</Field>
          <Field label="Comment">{invoice.comment ?? <NotRecorded />}</Field>
        </dl>
      </Card>

      <Card>
        <CardHeader
          title="Line items"
          subtitle={`${invoice.lines.length} ${invoice.lines.length === 1 ? "line" : "lines"} · benefit products and fees billed on this invoice`}
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[600px] border-collapse text-[13.5px]">
            <thead>
              <tr className="border-y border-rule bg-paper/60 text-left text-[11.5px] font-semibold tracking-[0.06em] text-muted uppercase">
                <th scope="col" className="px-5 py-2.5 font-semibold">#</th>
                <th scope="col" className="px-5 py-2.5 font-semibold">Item</th>
                <th scope="col" className="px-5 py-2.5 font-semibold">Description</th>
                <th scope="col" className="px-5 py-2.5 font-semibold">Carrier</th>
                <th scope="col" className="px-5 py-2.5 text-right font-semibold">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {invoice.lines.map((line, index) => (
                <tr key={line.line_no}>
                  <td className="px-5 py-3 text-muted tabular-nums">{index + 1}</td>
                  <td className="px-5 py-3 whitespace-nowrap tabular-nums">{line.item_code}</td>
                  <td className="px-5 py-3">{line.description ?? <NotRecorded />}</td>
                  <td className="px-5 py-3">{line.carrier_code ?? <NotRecorded />}</td>
                  <td className="px-5 py-3 text-right whitespace-nowrap">
                    <Amount value={line.amount} />
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-rule-firm">
                <th scope="row" colSpan={4} className="px-5 py-3 text-right font-semibold">
                  Invoice total
                </th>
                <td className="px-5 py-3 text-right font-semibold whitespace-nowrap">
                  <Amount value={invoice.amount} />
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
        {!linesMatch && (
          // Never seen in verified data; shown so a future sync problem is not hidden.
          <p role="alert" className="flex items-center gap-2 border-t border-rule px-5 py-3 text-[13px] text-negative">
            <AlertTriangle size={15} aria-hidden />
            The line items add up to <Amount value={invoice.lines_total} />, which differs from the invoice amount. The
            invoice amount is the authoritative total.
          </p>
        )}
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[12px] font-medium text-muted">{label}</dt>
      <dd className="mt-1 font-medium">{children}</dd>
    </div>
  );
}

/** Distinguishes "no value in the source data" from an empty string or zero. */
function NotRecorded() {
  return <span className="font-normal text-muted italic">Not recorded</span>;
}

export function InvoiceDetailSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-label="Loading invoice">
      <Skeleton className="h-8 w-56" />
      <Card className="grid grid-cols-2 gap-6 p-5 lg:grid-cols-4">
        {Array.from({ length: 8 }, (_, i) => (
          <div key={i}>
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-2 h-4 w-32" />
          </div>
        ))}
      </Card>
      <Card>
        <TableSkeleton rows={4} />
      </Card>
    </div>
  );
}
