import { Suspense } from "react";
import { Card, TableSkeleton } from "@/components/ui";
import { ReportsView } from "./reports-view";

export default function ReportsPage() {
  return (
    <Suspense
      fallback={
        <Card>
          <TableSkeleton rows={10} />
        </Card>
      }
    >
      <ReportsView />
    </Suspense>
  );
}
