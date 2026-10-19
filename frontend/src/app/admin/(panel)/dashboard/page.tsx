import { Suspense } from "react";
import { DashboardSkeleton, DashboardView } from "./dashboard-view";

export default function DashboardPage() {
  // The view reads its date filter from the URL, which needs a Suspense boundary.
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <DashboardView />
    </Suspense>
  );
}
