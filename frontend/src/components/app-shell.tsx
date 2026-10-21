"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, Search, X, type LucideIcon } from "lucide-react";
import { apiPost, useApi, type CurrentUser } from "@/lib/api";
import { inputStyles } from "@/components/ui";

/** What the shell shows for one area of the app (admin or customer). */
export type ShellConfig = {
  brandHref: string;
  subtitle: string;
  nav: { href: string; label: string; icon: LucideIcon; exact?: boolean }[];
  /** Where sign-out and an expired session go. */
  signInHref: string;
  /** Global search in the top bar. Hidden while the user is already on `listPath`. */
  search?: { listPath: string; placeholder: string };
};

function isActive(pathname: string, item: ShellConfig["nav"][number]) {
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

// ---------- Remembered collapse state ----------
// localStorage can throw (private mode, blocked storage); the in-memory value
// keeps the toggle working for the current visit in that case.

const COLLAPSE_KEY = "bnd.sidebarCollapsed";
const COLLAPSE_EVENT = "bnd-sidebar-change";
let collapsedFallback = false;

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return collapsedFallback;
  }
}

function writeCollapsed(value: boolean) {
  collapsedFallback = value;
  try {
    window.localStorage.setItem(COLLAPSE_KEY, value ? "1" : "0");
  } catch {
    // storage unavailable: the fallback above still applies
  }
  window.dispatchEvent(new Event(COLLAPSE_EVENT));
}

function subscribeCollapsed(onChange: () => void) {
  window.addEventListener(COLLAPSE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(COLLAPSE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function useSidebarCollapsed() {
  // Server render and first paint use "expanded"; the stored value applies right after.
  return useSyncExternalStore(subscribeCollapsed, readCollapsed, () => false);
}

// ---------- Shell ----------

export function AppShell({ children, config }: { children: React.ReactNode; config: ShellConfig }) {
  const pathname = usePathname();
  const collapsed = useSidebarCollapsed();
  const [drawer, setDrawer] = useState({ open: false, pathname });

  // Close the mobile drawer whenever the route changes.
  if (drawer.pathname !== pathname) setDrawer({ open: false, pathname });
  const drawerOpen = drawer.open;
  const setDrawerOpen = (open: boolean) => setDrawer({ open, pathname });

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer((d) => ({ ...d, open: false }));
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="min-h-screen">
      {/* Mobile overlay */}
      <div
        aria-hidden
        onClick={() => setDrawerOpen(false)}
        className={`fixed inset-0 z-30 bg-ink/30 transition-opacity lg:hidden ${
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        aria-label="Sidebar"
        className={`fixed inset-y-0 left-0 z-40 flex w-[256px] flex-col border-r border-rule bg-surface transition-[width,translate] duration-200 ease-out
          ${drawerOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0
          ${collapsed ? "lg:w-[72px]" : "lg:w-[256px]"}`}
      >
        <SidebarHeader config={config} collapsed={collapsed} onCloseDrawer={() => setDrawerOpen(false)} />
        <nav aria-label="Main" className="flex-1 px-3 py-4">
          <p className={`mb-2 px-3 text-[11px] font-semibold tracking-[0.12em] text-muted uppercase ${collapsed ? "lg:sr-only" : ""}`}>
            Reporting
          </p>
          <ul className="space-y-1">
            {config.nav.map((item) => (
              <li key={item.href}>
                <NavLink {...item} active={isActive(pathname, item)} collapsed={collapsed} />
              </li>
            ))}
          </ul>
        </nav>
        <UserBlock collapsed={collapsed} signInHref={config.signInHref} />
      </aside>

      <div className={`transition-[padding] duration-200 ease-out ${collapsed ? "lg:pl-[72px]" : "lg:pl-[256px]"}`}>
        <TopBar pathname={pathname} search={config.search} onOpenDrawer={() => setDrawerOpen(true)} />
        <main className="mx-auto max-w-[1360px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

function SidebarHeader({
  config,
  collapsed,
  onCloseDrawer,
}: {
  config: ShellConfig;
  collapsed: boolean;
  onCloseDrawer: () => void;
}) {
  return (
    <div className={`flex h-16 items-center border-b border-rule px-4 ${collapsed ? "lg:justify-center lg:px-0" : "justify-between"}`}>
      <Link href={config.brandHref} className={`flex items-center gap-2.5 ${collapsed ? "lg:hidden" : ""}`}>
        <span aria-hidden className="flex h-8 w-8 items-center justify-center rounded-md bg-signal text-[14px] font-bold text-white">
          B
        </span>
        <span className="leading-tight">
          <span className="block text-[14px] font-semibold">BND Reporting</span>
          <span className="block text-[12px] text-muted">{config.subtitle}</span>
        </span>
      </Link>
      <button
        type="button"
        onClick={() => writeCollapsed(!collapsed)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="hidden h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-paper hover:text-ink lg:flex"
      >
        {collapsed ? <PanelLeftOpen size={18} aria-hidden /> : <PanelLeftClose size={18} aria-hidden />}
      </button>
      <button
        type="button"
        onClick={onCloseDrawer}
        aria-label="Close menu"
        className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-paper hover:text-ink lg:hidden"
      >
        <X size={18} aria-hidden />
      </button>
    </div>
  );
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed,
}: ShellConfig["nav"][number] & { active: boolean; collapsed: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? label : undefined}
      className={`group relative flex h-10 items-center gap-3 rounded-md px-3 text-[14px] font-medium transition-colors
        ${collapsed ? "lg:justify-center lg:px-0" : ""}
        ${active ? "bg-signal-tint text-signal" : "text-ink-soft hover:bg-paper hover:text-ink"}`}
    >
      {active && <span aria-hidden className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-signal" />}
      <Icon size={18} aria-hidden className="shrink-0" />
      <span className={collapsed ? "lg:hidden" : ""}>{label}</span>
      {collapsed && (
        // Tooltip for the icon-only sidebar (desktop only).
        <span
          role="tooltip"
          className="pointer-events-none absolute left-full z-50 ml-3 hidden rounded-md bg-ink px-2.5 py-1 text-[12.5px] whitespace-nowrap text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 lg:block"
        >
          {label}
        </span>
      )}
    </Link>
  );
}

function UserBlock({ collapsed, signInHref }: { collapsed: boolean; signInHref: string }) {
  // A 401 here (expired session) redirects to the sign-in page inside the API helper.
  const { data: user } = useApi<CurrentUser>("/api/auth/me");
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  async function signOut() {
    setSigningOut(true);
    try {
      await apiPost("/api/auth/logout");
    } finally {
      // In-app navigation, no page reload. replace() keeps "Back" from returning to a signed-in page.
      router.replace(signInHref);
    }
  }

  return (
    <div className={`flex items-center gap-3 border-t border-rule p-3 ${collapsed ? "lg:flex-col lg:gap-2" : ""}`}>
      <span
        aria-hidden
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-paper text-[13px] font-semibold text-ink-soft uppercase"
      >
        {user?.email?.charAt(0) ?? ""}
      </span>
      <div className={`min-w-0 flex-1 ${collapsed ? "lg:hidden" : ""}`}>
        <p className="text-[12px] text-muted">Signed in as</p>
        <p className="truncate text-[13px] font-medium" title={user?.email ?? undefined}>
          {user?.email ?? "…"}
        </p>
      </div>
      <button
        type="button"
        onClick={signOut}
        disabled={signingOut}
        aria-label="Sign out"
        title="Sign out"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted hover:bg-paper hover:text-ink disabled:opacity-50"
      >
        <LogOut size={17} aria-hidden />
      </button>
    </div>
  );
}

function TopBar({
  pathname,
  search,
  onOpenDrawer,
}: {
  pathname: string;
  search: ShellConfig["search"];
  onOpenDrawer: () => void;
}) {
  const router = useRouter();
  // The list page has its own search field, so the global one is hidden there.
  const showSearch = Boolean(search) && !pathname.startsWith(search?.listPath ?? "");

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-rule bg-surface/95 px-4 backdrop-blur sm:px-6 lg:px-8">
      <button type="button" onClick={onOpenDrawer} aria-label="Open menu" className="-ml-1 flex h-9 w-9 items-center justify-center rounded-md text-ink-soft hover:bg-paper lg:hidden">
        <Menu size={20} aria-hidden />
      </button>
      {showSearch && search && (
        <form
          role="search"
          className="relative w-full max-w-md"
          onSubmit={(event) => {
            event.preventDefault();
            const q = String(new FormData(event.currentTarget).get("q") ?? "").trim();
            router.push(q ? `${search.listPath}?q=${encodeURIComponent(q)}` : search.listPath);
          }}
        >
          <Search size={16} aria-hidden className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
          <input
            name="q"
            type="search"
            aria-label="Search invoices"
            placeholder={search.placeholder}
            className={`${inputStyles} w-full bg-paper pl-9 focus:bg-surface`}
          />
        </form>
      )}
    </header>
  );
}
