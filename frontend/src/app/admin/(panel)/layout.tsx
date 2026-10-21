"use client";

import { Suspense } from "react";
import { FileText, LayoutDashboard, ListChecks, Receipt } from "lucide-react";
import { AppShell, type ShellConfig } from "@/components/app-shell";

const ADMIN_SHELL: ShellConfig = {
  brandHref: "/admin/dashboard",
  subtitle: "Invoice history",
  signInHref: "/admin",
  nav: [
    { href: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/admin/invoices", label: "Invoices", icon: Receipt },
    { href: "/admin/reports", label: "Reports", icon: FileText },
    // { href: "/admin/review-queue", label: "Review queue", icon: ListChecks },
  ],
  // search: { listPath: "/admin/invoices", placeholder: "Search invoice no, member no or name…" },
};

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  // The shell reads the current path (active nav item, drawer), which Next.js only
  // knows at request time for dynamic routes such as /invoices/[no]/[seq].
  return (
    <Suspense fallback={<ShellPlaceholder />}>
      <AppShell config={ADMIN_SHELL}>{children}</AppShell>
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
