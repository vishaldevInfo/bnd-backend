// Unit tests for display formatting. Run: npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { formatAmount, formatCount, formatDate, formatMonth, percentChange, setCurrency } from "../src/lib/format.ts";

test("amounts use 2 decimals and the configured currency", () => {
  setCurrency("USD");
  assert.equal(formatAmount("1234.5"), "$1,234.50");
  assert.equal(formatAmount("-256.89"), "-$256.89");
  assert.equal(formatAmount("0"), "$0.00");
});

test("missing amounts show a dash, not zero", () => {
  assert.equal(formatAmount(null), "—");
  assert.equal(formatAmount(undefined), "—");
});

test("a non-ISO currency label falls back to number + label", () => {
  setCurrency("POINTS");
  assert.equal(formatAmount("10"), "10.00 POINTS");
  setCurrency("USD");
});

test("compact amounts for chart axes", () => {
  assert.equal(formatAmount(450000, { compact: true }), "$450K");
});

test("dates are calendar dates, never shifted by time zone", () => {
  assert.equal(formatDate("2026-03-07"), "Mar 7, 2026");
  assert.equal(formatDate("2026-01-01"), "Jan 1, 2026");
  assert.equal(formatDate(null), "—");
  assert.equal(formatMonth("2026-03-01"), "Mar 2026");
});

test("percent change needs a non-zero base", () => {
  assert.equal(percentChange(110, 100), 10);
  assert.equal(percentChange(90, 100), -10);
  assert.equal(percentChange(5, 0), null);
  assert.equal(percentChange(5, null), null);
});

test("counts use thousands separators", () => {
  assert.equal(formatCount(27691), "27,691");
});
