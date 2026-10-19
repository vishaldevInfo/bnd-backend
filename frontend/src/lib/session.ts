// Session helpers shared by the sign-in pages. The session itself is an HTTP-only
// cookie that JavaScript cannot read, so the role always comes from /api/auth/me.
import type { CurrentUser } from "@/lib/api";

/** Only in-app paths are allowed as redirect targets (blocks //evil.com and absolute URLs). */
export function safeNextPath(fallback: string): string {
  const next = new URLSearchParams(window.location.search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}

/** The signed-in user, or null when nobody is signed in. Never redirects. */
export async function currentUser(): Promise<CurrentUser | null> {
  try {
    const response = await fetch("/api/auth/me", { credentials: "same-origin", cache: "no-store" });
    return response.ok ? ((await response.json()) as CurrentUser) : null;
  } catch {
    return null;
  }
}

/** Where each role lands after signing in. */
export const HOME_FOR_ROLE = { admin: "/admin/dashboard", end_user: "/portal" } as const;
