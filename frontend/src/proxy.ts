import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Optimistic check only: sends visitors without a session cookie to /login.
// The cookie's signature and expiry are verified by FastAPI on every API call,
// and an expired session is redirected to /login by lib/api.ts.
const SESSION_COOKIE = "bnd_session";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  if (!hasSession && pathname !== "/login") {
    const loginUrl = new URL("/login", request.url);
    if (pathname !== "/") loginUrl.searchParams.set("next", pathname + search);
    return NextResponse.redirect(loginUrl);
  }
  // Signed-in users have no reason to see the login form. (An expired cookie is
  // deleted by the backend on its first 401, so this cannot loop.)
  if (hasSession && pathname === "/login") {
    return NextResponse.redirect(new URL("/", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Skip API calls (FastAPI handles those), Next.js assets and the favicon.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
