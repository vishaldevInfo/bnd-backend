import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Optimistic check only: it sends visitors without a session cookie to the right
// sign-in page. It cannot tell the roles apart (the cookie is HTTP-only), so the
// backend decides what each signed-in user may see on every API call. The sign-in
// pages ask /api/auth/me and send each role to its own home.
const SESSION_COOKIE = "bnd_session";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }

  if (pathname === "/") {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (pathname.startsWith("/admin/")) {
    return redirectTo("/admin", pathname + search, request);
  }
  if (pathname === "/portal" || pathname.startsWith("/portal/")) {
    return redirectTo("/login", pathname + search, request);
  }
  return NextResponse.next();
}

function redirectTo(signIn: string, next: string, request: NextRequest) {
  const url = new URL(signIn, request.url);
  url.searchParams.set("next", next);
  return NextResponse.redirect(url);
}

export const config = {
  // Skip API calls (FastAPI handles those), Next.js assets and the favicon.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
