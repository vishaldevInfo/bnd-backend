import { Suspense } from "react";
import { InvoiceDetailSkeleton, InvoiceDetailView } from "./invoice-detail-view";

export default function InvoiceDetailPage() {
  return (
    <Suspense fallback={<InvoiceDetailSkeleton />}>
      <InvoiceDetailView />
    </Suspense>
  );
}
