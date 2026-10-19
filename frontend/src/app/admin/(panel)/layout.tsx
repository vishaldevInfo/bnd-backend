import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  // The shell reads the current path (active nav item, drawer), which Next.js only
  // knows at request time for dynamic routes such as /invoices/[no]/[seq].
  return (
    <Suspense fallback={<ShellPlaceholder />}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}

function ShellPlaceholder() {
  return (
    <div className="min-h-screen lg:pl-[256px]" aria-busy>
      <div className="fixed inset-y-0 left-0 hidden w-[256px] border-r border-rule bg-surface lg:block" />
      <div className="h-16 border-b border-rule bg-surface" />
    </div>
  );
}
