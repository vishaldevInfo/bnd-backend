import { Suspense } from "react";
import { InvoicesView } from "./invoices-view";

export default function PortalInvoicesPage() {
  return (
    <Suspense fallback={<div className="h-64" role="status" aria-label="Loading your invoices" />}>
      <InvoicesView />
    </Suspense>
  );
}
