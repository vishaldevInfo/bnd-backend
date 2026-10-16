import { Suspense } from "react";
import { Card, TableSkeleton } from "@/components/ui";
import { InvoicesView } from "./invoices-view";

export default function InvoicesPage() {
  return (
    <Suspense
      fallback={
        <Card>
          <TableSkeleton rows={10} />
        </Card>
      }
    >
      <InvoicesView />
    </Suspense>
  );
}
