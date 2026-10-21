"use client";

import { Suspense } from "react";
import { LayoutDashboard, Receipt } from "lucide-react";
import { AppShell, type ShellConfig } from "@/components/app-shell";

const CUSTOMER_SHELL: ShellConfig = {
  brandHref: "/portal",
  subtitle: "Your invoices",
  signInHref: "/login",
  nav: [
    { href: "/portal", label: "Dashboard", icon: LayoutDashboard, exact: true },
    { href: "/portal/invoices", label: "Invoices", icon: Receipt },
  ],
  search: { listPath: "/portal/invoices", placeholder: "Search invoice number…" },
};

/** Customer area: the same sidebar and top bar as the admin area, with customer pages only. */
export default function PortalLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen" aria-busy />}>
      <AppShell config={CUSTOMER_SHELL}>{children}</AppShell>
    </Suspense>
  );
}
