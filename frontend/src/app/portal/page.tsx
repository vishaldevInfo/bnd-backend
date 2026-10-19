"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Card, CardHeader, Amount, EmptyState, ErrorState, TableSkeleton } from "@/components/ui";
import { apiPath, apiPost, useApi, type InvoicePage } from "@/lib/api";
import { formatDate } from "@/lib/format";

/** Customer home: the signed-in customer's own invoices. The backend limits the list to their customer number. */
export default function PortalPage() {
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);
  const { data, error, loading, reload } = useApi<InvoicePage>(
    apiPath("/api/invoices", { sort: "invoice_date", order: "desc", page_size: 100 }),
  );

  async function signOut() {
    setSigningOut(true);
    try {
      await apiPost("/api/auth/logout", undefined, false);
    } finally {
      router.replace("/login");
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-[900px] px-4 py-8 sm:px-6">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <span aria-hidden className="flex h-9 w-9 items-center justify-center rounded-md bg-signal text-[15px] font-bold text-white">
            B
          </span>
          <span className="text-[16px] font-semibold">BND Reporting</span>
        </div>
        <button
          type="button"
          onClick={signOut}
          disabled={signingOut}
          className="h-9 rounded-md border border-rule px-3 text-[13.5px] font-medium text-ink-soft hover:text-ink disabled:opacity-60"
        >
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </header>

      <Card>
        <CardHeader title="Your invoices" subtitle={data ? `${data.total} invoice${data.total === 1 ? "" : "s"}` : undefined} />
        {loading && <TableSkeleton rows={6} columns={3} />}
        {error && <ErrorState message={error} onRetry={reload} />}
        {data && data.items.length === 0 && (
          <EmptyState title="No invoices yet" message="Invoices for your account will appear here." />
        )}
        {data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-[13.5px]">
              <thead>
                <tr className="border-y border-rule bg-paper/60 text-left text-[11.5px] font-semibold tracking-[0.06em] text-muted uppercase">
                  <th scope="col" className="px-4 py-2.5">Invoice</th>
                  <th scope="col" className="px-4 py-2.5">Date</th>
                  <th scope="col" className="px-4 py-2.5 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={`${row.invoice_no}-${row.header_seq}`} className="border-b border-rule last:border-0">
                    <td className="px-4 py-3 font-medium">{row.invoice_no}</td>
                    <td className="px-4 py-3 text-ink-soft">{formatDate(row.invoice_date)}</td>
                    <td className="px-4 py-3 text-right"><Amount value={row.amount} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </main>
  );
}
