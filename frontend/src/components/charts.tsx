// Recharts wrappers with the shared dark styling: recessive grid, 2px lines,
// crosshair + tooltip on time series, per-bar tooltip on bars.

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDate, formatEur, formatEurCompact, formatMonthTick } from "../lib/format";
import { firstDatePerMonth } from "../lib/ranges";

export interface SeriesSpec {
  key: string;
  label: string;
  color: string;
  dashed?: boolean;
}

const AXIS_PROPS = {
  stroke: "var(--text-muted)",
  tick: { fill: "var(--text-muted)", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;

const GRID = <CartesianGrid stroke="var(--border)" strokeDasharray="0" vertical={false} />;
const CURSOR_LINE = { stroke: "var(--text-muted)", strokeWidth: 1 };

interface TooltipEntry {
  dataKey?: string | number;
  value?: number | null;
}

function ChartTooltip({
  active,
  payload,
  label,
  series,
  formatLabel,
  showTotal,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
  series: SeriesSpec[];
  formatLabel: (label: string) => string;
  showTotal?: boolean;
}) {
  if (!active || !payload?.length || label === undefined) return null;
  const valueByKey = new Map(payload.map((entry) => [String(entry.dataKey), entry.value ?? null]));
  const total = series.reduce((sum, spec) => sum + (valueByKey.get(spec.key) ?? 0), 0);
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{formatLabel(label)}</div>
      {/* Top-down order matches the stack / legend order */}
      {[...series].reverse().map((spec) => (
        <div key={spec.key} className="chart-tooltip-row">
          <span className="chart-tooltip-name">
            <span className="legend-swatch" style={{ background: spec.color }} />
            {spec.label}
          </span>
          <span className="chart-tooltip-value">{formatEur(valueByKey.get(spec.key))}</span>
        </div>
      ))}
      {showTotal && (
        <div className="chart-tooltip-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 4, marginTop: 6 }}>
          <span className="chart-tooltip-name">Total</span>
          <span className="chart-tooltip-value">{formatEur(total)}</span>
        </div>
      )}
    </div>
  );
}

/** Stacked areas over time: parts of a whole (e.g. cash + investments = net worth). */
export function StackedAreaChart({
  data,
  series,
  height = 300,
  xKey = "date",
  formatLabel = formatDate,
}: {
  data: Record<string, unknown>[];
  series: SeriesSpec[];
  height?: number;
  xKey?: string;
  formatLabel?: (label: string) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        {GRID}
        <XAxis
          dataKey={xKey}
          {...AXIS_PROPS}
          ticks={firstDatePerMonth(data.map((point) => String(point[xKey])))}
          tickFormatter={formatMonthTick}
          minTickGap={40}
        />
        <YAxis {...AXIS_PROPS} tickFormatter={formatEurCompact} width={70} />
        <Tooltip
          cursor={CURSOR_LINE}
          content={<ChartTooltip series={series} formatLabel={formatLabel} showTotal />}
        />
        {series.map((spec) => (
          <Area
            key={spec.key}
            type="monotone"
            dataKey={spec.key}
            stackId="stack"
            stroke={spec.color}
            strokeWidth={2}
            fill={spec.color}
            fillOpacity={0.28}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

/** Lines over time on a single EUR axis (e.g. market value vs invested). */
export function TimeLineChart({
  data,
  series,
  height = 300,
  xKey = "date",
  formatLabel = formatDate,
}: {
  data: Record<string, unknown>[];
  series: SeriesSpec[];
  height?: number;
  xKey?: string;
  formatLabel?: (label: string) => string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        {GRID}
        <XAxis
          dataKey={xKey}
          {...AXIS_PROPS}
          ticks={firstDatePerMonth(data.map((point) => String(point[xKey])))}
          tickFormatter={formatMonthTick}
          minTickGap={40}
        />
        <YAxis {...AXIS_PROPS} tickFormatter={formatEurCompact} width={70} domain={["auto", "auto"]} />
        <Tooltip cursor={CURSOR_LINE} content={<ChartTooltip series={series} formatLabel={formatLabel} />} />
        {series.map((spec) => (
          <Line
            key={spec.key}
            type="monotone"
            dataKey={spec.key}
            stroke={spec.dashed ? "var(--text-secondary)" : spec.color}
            strokeWidth={2}
            strokeDasharray={spec.dashed ? "5 4" : undefined}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Monthly bars, grouped side by side when there are several series. */
export function MonthlyBarChart({
  data,
  series,
  height = 260,
}: {
  data: Record<string, unknown>[];
  series: SeriesSpec[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="22%">
        {GRID}
        <XAxis dataKey="month" {...AXIS_PROPS} tickFormatter={formatMonthTick} />
        <YAxis {...AXIS_PROPS} tickFormatter={formatEurCompact} width={70} />
        <Tooltip
          cursor={{ fill: "var(--surface-2)" }}
          content={<ChartTooltip series={series} formatLabel={formatMonthTick} />}
        />
        {series.map((spec) => (
          <Bar
            key={spec.key}
            dataKey={spec.key}
            fill={spec.color}
            radius={[4, 4, 0, 0]}
            maxBarSize={28}
            isAnimationActive={false}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Yearly ticks ("YYYY-01") so long projections stay readable. */
function januaryTicks(months: string[]): string[] {
  return months.filter((month, index) => index === 0 || month.endsWith("-01"));
}

function ProjectionTooltip({
  active,
  payload,
  label,
  series,
  activeKey,
}: {
  active?: boolean;
  payload?: { dataKey?: string | number; value?: number | [number, number] }[];
  label?: string;
  series: SeriesSpec[];
  activeKey: string;
}) {
  if (!active || !payload?.length || label === undefined) return null;
  const valueByKey = new Map(payload.map((entry) => [String(entry.dataKey), entry.value]));
  const band = valueByKey.get("band") as [number, number] | undefined;
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{formatMonthTick(label)}</div>
      {series.map((spec) => (
        <div key={spec.key} className="chart-tooltip-row">
          <span className="chart-tooltip-name">
            <span className="legend-swatch" style={{ background: spec.color }} />
            {spec.label}
          </span>
          <span className="chart-tooltip-value">{formatEur(valueByKey.get(spec.key) as number | undefined)}</span>
        </div>
      ))}
      {band && (
        <div className="chart-tooltip-row" style={{ borderTop: "1px solid var(--border)", paddingTop: 4, marginTop: 6 }}>
          <span className="chart-tooltip-name">{activeKey}: 80 % de los casos</span>
          <span className="chart-tooltip-value">
            {formatEurCompact(band[0])} – {formatEurCompact(band[1])}
          </span>
        </div>
      )}
    </div>
  );
}

/** Scenario lines on one EUR axis, with the active scenario's p10–p90 band behind them. */
export function ProjectionChart({
  data,
  series,
  activeKey,
  activeColor,
  height = 340,
}: {
  data: Record<string, unknown>[];
  series: SeriesSpec[];
  activeKey: string;
  activeColor: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        {GRID}
        <XAxis
          dataKey="month"
          {...AXIS_PROPS}
          ticks={januaryTicks(data.map((row) => String(row.month)))}
          tickFormatter={(month: string) => month.slice(0, 4)}
          minTickGap={24}
        />
        <YAxis {...AXIS_PROPS} tickFormatter={formatEurCompact} width={70} />
        <Tooltip cursor={CURSOR_LINE} content={<ProjectionTooltip series={series} activeKey={activeKey} />} />
        <Area
          dataKey="band"
          stroke="none"
          fill={activeColor}
          fillOpacity={0.14}
          isAnimationActive={false}
          activeDot={false}
        />
        {series.map((spec) => (
          <Line
            key={spec.key}
            type="monotone"
            dataKey={spec.key}
            stroke={spec.color}
            strokeWidth={spec.key === activeKey ? 2.5 : 1.5}
            strokeOpacity={spec.key === activeKey ? 1 : 0.7}
            dot={false}
            activeDot={{ r: 4, stroke: "var(--surface-1)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
