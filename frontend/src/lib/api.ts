// Fetch helpers and API types shared by every page. Requests go to /api/*, which
// Next.js forwards to FastAPI (see next.config.ts). The session lives in an
// HTTP-only cookie that the browser sends automatically.
import { useCallback, useEffect, useState } from "react";
import { setCurrency } from "@/lib/format";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Session expired or wrong role: go to the matching sign-in page and come back here afterwards.
 * Admin pages return to /admin, customer pages to /login. (Plain helper outside React, so it cannot use the Next.js router.) */
function redirectToLogin() {
  const next = window.location.pathname + window.location.search;
  const signIn = window.location.pathname.startsWith("/admin") ? "/admin" : "/login";
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- runs outside React, no router here
  window.location.href = `${signIn}?next=${encodeURIComponent(next)}`;
}

async function request<T>(path: string, init: RequestInit, redirectOnUnauthorized: boolean): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { credentials: "same-origin", cache: "no-store", ...init });
  } catch {
    throw new ApiError("Cannot reach the server. Check that the backend is running.", 0);
  }

  // 403 means "signed in, but not for this area" (an end user on an admin page), so sign-in is the next step.
  if ((response.status === 401 || response.status === 403) && redirectOnUnauthorized) {
    redirectToLogin();
  }

  const body = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}).`;
    throw new ApiError(detail, response.status);
  }
  if (typeof body?.currency === "string") setCurrency(body.currency);
  return body as T;
}

/** GET a JSON endpoint. An expired session sends the user to the login page. */
export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, {}, true);
}

/** POST JSON. Pass redirectOnUnauthorized=false where 401 is an expected answer (login form). */
export function apiPost<T>(path: string, body?: unknown, redirectOnUnauthorized = true): Promise<T> {
  return request<T>(
    path,
    {
      method: "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
    redirectOnUnauthorized,
  );
}

/** Builds "/api/x?a=1&b=2", leaving out empty values. */
export function apiPath(path: string, params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

type ApiState<T> = { data: T | null; error: string | null; loading: boolean; reload: () => void };

/** Loads `path` whenever it changes. Responses for an outdated path are ignored. */
export function useApi<T>(path: string | null): ApiState<T> {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null }>({
    path: null, data: null, error: null,
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!path) return;
    let current = true;
    apiGet<T>(path)
      .then((data) => current && setState({ path, data, error: null }))
      .catch((e: Error) => current && setState({ path, data: null, error: e.message }));
    return () => {
      current = false;
    };
  }, [path, attempt]);

  const reload = useCallback(() => {
    setState((s) => ({ ...s, path: null }));
    setAttempt((n) => n + 1);
  }, []);

  const settled = state.path === path;
  return {
    data: settled ? state.data : null,
    error: settled ? state.error : null,
    loading: Boolean(path) && !settled,
    reload,
  };
}

// ---------- API types (mirror backend/app/schemas.py) ----------

export type CurrentUser = {
  role: "admin" | "end_user";
  email: string | null;
  customerno: string | null;
};

export type InvoiceRow = {
  invoice_no: string;
  header_seq: string;
  invoice_date: string;
  member_no: string;
  member_name: string;
  facility_code: string;
  facility_name: string;
  facility_known: boolean;
  amount: string;
};

export type InvoicePage = { items: InvoiceRow[]; total: number; page: number; page_size: number; currency: string };

export type InvoiceLine = {
  line_no: string;
  item_code: string;
  description: string | null;
  carrier_code: string | null;
  amount: string;
};

export type InvoiceDetail = InvoiceRow & {
  due_date: string | null;
  terms_code: string | null;
  comment: string | null;
  taxable_amount: string;
  non_taxable_amount: string;
  lines: InvoiceLine[];
  lines_total: string;
  currency: string;
};

export type Facility = { facility_code: string; facility_name: string; facility_known: boolean };

export type PeriodTotals = {
  start: string | null;
  end: string | null;
  invoice_count: number;
  total_amount: string;
  average_amount: string | null;
  active_facilities: number;
};

export type DashboardSummary = {
  currency: string;
  first_invoice_date: string | null;
  last_invoice_date: string | null;
  current: PeriodTotals;
  previous: PeriodTotals | null;
  monthly: { month: string; invoice_count: number; total_amount: string }[];
  top_facilities: (Facility & { invoice_count: number; total_amount: string })[];
  recent_invoices: InvoiceRow[];
};

export type InvoiceReport = {
  start: string | null;
  end: string | null;
  invoice_count: number;
  total_amount: string;
  currency: string;
  rows: InvoiceRow[];
  page: number;
  page_size: number;
};

export function invoiceHref(row: Pick<InvoiceRow, "invoice_no" | "header_seq">) {
  return `/admin/invoices/${encodeURIComponent(row.invoice_no)}/${encodeURIComponent(row.header_seq)}`;
}
