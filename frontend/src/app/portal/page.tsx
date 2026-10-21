import { Suspense } from "react";
import { DashboardView } from "./dashboard-view";

export default function PortalDashboardPage() {
  // The view reads its date filter from the URL, which needs a Suspense boundary.
  return (
    <Suspense fallback={<div className="h-64" role="status" aria-label="Loading your dashboard" />}>
      <DashboardView />
    </Suspense>
  );
}
