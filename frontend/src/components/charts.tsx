"use client";

import { useRouter } from "next/navigation";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DashboardSummary } from "@/lib/api";
import { formatAmount, formatCount, formatMonth } from "@/lib/format";

// Same values as --color-chart / --color-chart-grid / --color-muted in globals.css.
// Recharts writes SVG attributes, so the hex values are repeated here.
const CHART_COLOR = "#0891b2";
const GRID_COLOR = "#e6ecf0";
const AXIS_TEXT = { fill: "#5c6878", fontSize: 12 };

type Monthly = DashboardSummary["monthly"];
type TopFacilities = DashboardSummary["top_facilities"];

function ChartTooltip({ title, amount, count }: { title: string; amount: string; count: number }) {
  return (
    <div className="rounded-md border border-rule bg-surface px-3 py-2 text-[12.5px] shadow-sm">
      <p className="mb-1 font-semibold">{title}</p>
      <p className="tabular-nums">{formatAmount(amount)}</p>
      <p className="text-muted tabular-nums">{formatCount(count)} invoices</p>
    </div>
  );
}

/** Screen-reader table with the exact values behind a chart. */
function ChartDataTable({ caption, rows }: { caption: string; rows: [string, string, number][] }) {
  return (
    <table className="sr-only">
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Period or facility</th>
          <th scope="col">Amount</th>
          <th scope="col">Invoices</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([label, amount, count]) => (
          <tr key={label}>
            <th scope="row">{label}</th>
            <td>{formatAmount(amount)}</td>
            <td>{formatCount(count)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MonthlyAmountChart({ data }: { data: Monthly }) {
  const points = data.map((m) => ({ ...m, value: Number(m.total_amount) }));
  return (
    <>
      <div className="h-[280px] px-2 pb-3" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <defs>
              <linearGradient id="monthlyFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={CHART_COLOR} stopOpacity={0.18} />
                <stop offset="100%" stopColor={CHART_COLOR} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={GRID_COLOR} />
            <XAxis
              dataKey="month"
              tickFormatter={formatMonth}
              tick={AXIS_TEXT}
              tickLine={false}
              axisLine={{ stroke: GRID_COLOR }}
              minTickGap={24}
            />
            <YAxis
              tickFormatter={(v: number) => formatAmount(v, { compact: true })}
              tick={AXIS_TEXT}
              tickLine={false}
              axisLine={false}
              width={64}
            />
            <Tooltip
              cursor={{ stroke: "#c2ccd6", strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                const point = active && payload?.[0]?.payload;
                return point ? (
                  <ChartTooltip title={formatMonth(point.month)} amount={point.total_amount} count={point.invoice_count} />
                ) : null;
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={CHART_COLOR}
              strokeWidth={2}
              fill="url(#monthlyFill)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#ffffff", fill: CHART_COLOR }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable
        caption="Billed amount per month"
        rows={data.map((m) => [formatMonth(m.month), m.total_amount, m.invoice_count])}
      />
    </>
  );
}

const FACILITY_LABEL_MAX = 18;

/** One-line facility label; Recharts' default tick wraps long names onto two lines. */
function FacilityTick({ x, y, payload }: { x?: number | string; y?: number | string; payload?: { value: string } }) {
  const name = payload?.value ?? "";
  const label = name.length > FACILITY_LABEL_MAX ? `${name.slice(0, FACILITY_LABEL_MAX - 1).trimEnd()}…` : name;
  return (
    <text x={Number(x) - 8} y={Number(y)} dy={4} textAnchor="end" {...AXIS_TEXT}>
      <title>{name}</title>
      {label}
    </text>
  );
}

export function TopFacilitiesChart({ data }: { data: TopFacilities }) {
  const router = useRouter();
  const bars = data.map((f) => ({ ...f, value: Number(f.total_amount) }));
  return (
    <>
      <div className="px-2 pb-3" style={{ height: Math.max(160, bars.length * 34 + 40) }} aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 8 }} barCategoryGap={8}>
            <CartesianGrid horizontal={false} stroke={GRID_COLOR} />
            <XAxis
              type="number"
              tickFormatter={(v: number) => formatAmount(v, { compact: true })}
              tick={AXIS_TEXT}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="facility_name"
              width={140}
              tick={FacilityTick}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: "#f4f7f9" }}
              content={({ active, payload }) => {
                const bar = active && payload?.[0]?.payload;
                return bar ? (
                  <ChartTooltip title={bar.facility_name} amount={bar.total_amount} count={bar.invoice_count} />
                ) : null;
              }}
            />
            <Bar
              dataKey="value"
              fill={CHART_COLOR}
              radius={[0, 4, 4, 0]}
              maxBarSize={18}
              cursor="pointer"
              isAnimationActive={false}
              onClick={(bar: { payload?: { facility_code: string } }) => {
                if (bar.payload) router.push(`/invoices?facility=${encodeURIComponent(bar.payload.facility_code)}`);
              }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable
        caption="Top facilities by billed amount"
        rows={data.map((f) => [f.facility_name, f.total_amount, f.invoice_count])}
      />
    </>
  );
}
