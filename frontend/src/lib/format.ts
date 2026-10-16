// Display formatting shared by every page. Amounts arrive from the API as
// decimal strings ("1234.50") and are only converted for display.

let currencyCode = "USD";

/** Set once from the API's `currency` field (AMOUNT_CURRENCY_LABEL on the backend). */
export function setCurrency(code: string) {
  currencyCode = code;
}

export function formatAmount(value: string | number | null | undefined, options: { compact?: boolean } = {}) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: options.compact ? 0 : 2,
      maximumFractionDigits: options.compact ? 1 : 2,
      notation: options.compact ? "compact" : "standard",
    }).format(number);
  } catch {
    // Label is not an ISO currency code: show the number followed by the label.
    return `${number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${currencyCode}`;
  }
}

export function formatCount(value: number) {
  return value.toLocaleString("en-US");
}

/** "2026-03-07" -> "Mar 7, 2026". Parsed as a calendar date, never shifted by time zone. */
export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day)).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric", timeZone: "UTC",
  });
}

/** "2026-03-01" -> "Mar 2026" */
export function formatMonth(value: string) {
  const [year, month] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString("en-US", {
    month: "short", year: "numeric", timeZone: "UTC",
  });
}

/** Percentage change, or null when there is no meaningful base (previous = 0 or missing). */
export function percentChange(current: number, previous: number | null | undefined) {
  if (previous === null || previous === undefined || previous === 0) return null;
  return ((current - previous) / Math.abs(previous)) * 100;
}

export function isNegative(value: string | number) {
  return Number(value) < 0;
}
