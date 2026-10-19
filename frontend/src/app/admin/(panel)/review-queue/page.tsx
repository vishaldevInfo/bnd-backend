"use client";

import { Card, CardHeader, EmptyState, ErrorState, PageHeader, TableSkeleton } from "@/components/ui";
import { useApi } from "@/lib/api";
import { formatDate } from "@/lib/format";

type ReviewItem = {
  id: string;
  submitted_first_name: string;
  submitted_last_name: string;
  candidate_count: number;
  status: "pending" | "resolved";
  created_at: string;
};

/** Customer lookups that matched more than one customer. Nothing is linked automatically: resolve each one by hand. */
export default function ReviewQueuePage() {
  const { data, error, loading, reload } = useApi<ReviewItem[]>("/api/admin/review-queue");

  return (
    <>
      <PageHeader
        title="Identity review queue"
        subtitle="Customer sign-up lookups that matched more than one customer. Each one needs a manual check."
      />
      <Card>
        <CardHeader title="Pending reviews" subtitle={data ? `${data.length} pending` : undefined} />
        {loading && <TableSkeleton rows={5} columns={4} />}
        {error && <ErrorState message={error} onRetry={reload} />}
        {data && data.length === 0 && (
          <EmptyState title="Nothing to review" message="Ambiguous sign-up lookups will appear here." />
        )}
        {data && data.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[13.5px]">
              <thead>
                <tr className="border-y border-rule bg-paper/60 text-left text-[11.5px] font-semibold tracking-[0.06em] text-muted uppercase">
                  <th scope="col" className="px-4 py-2.5">Submitted name</th>
                  <th scope="col" className="px-4 py-2.5">Candidates</th>
                  <th scope="col" className="px-4 py-2.5">Status</th>
                  <th scope="col" className="px-4 py-2.5">Received</th>
                </tr>
              </thead>
              <tbody>
                {data.map((item) => (
                  <tr key={item.id} className="border-b border-rule last:border-0">
                    <td className="px-4 py-3 font-medium">{item.submitted_first_name} {item.submitted_last_name}</td>
                    <td className="px-4 py-3">{item.candidate_count}</td>
                    <td className="px-4 py-3 capitalize text-ink-soft">{item.status}</td>
                    <td className="px-4 py-3 text-ink-soft">{formatDate(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
