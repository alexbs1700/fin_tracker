// Monthly distribution of the daily net worth: min, max, mean and median

import { useState } from "react";

import { useNetWorthMonthlyStats } from "../api/client";
import { formatEur, formatMonthTick } from "../lib/format";
import {
  changeOverCompleteMonths,
  NET_WORTH_VALUE_OPTIONS,
  type NetWorthValue,
  selectStatistics,
  STATISTIC_OPTIONS,
  type StatisticSelection,
} from "../lib/monthlyStats";
import { type RangeKey, rangeStartMonth } from "../lib/ranges";
import { MonthlyBarChart, TimeLineChart } from "./charts";
import { Card, Delta, ErrorState, Legend, RangeSelector, Segmented } from "./ui";

const STATISTIC_HINTS: Record<StatisticSelection, string> = {
  min_eur: "Lo que tuviste seguro durante todo el mes",
  max_eur: "El pico del mes, normalmente justo tras cobrar",
  mean_eur: "Saldo medio diario del mes",
  median_eur: "El valor típico del mes, sin que los picos lo distorsionen",
  compare: "Los cuatro estadísticos del mes a la vez",
};

export default function MonthlyStatsCard() {
  const [statistic, setStatistic] = useState<StatisticSelection>("min_eur");
  const [value, setValue] = useState<NetWorthValue>("total");
  const [range, setRange] = useState<RangeKey>("1A");

  const monthlyStats = useNetWorthMonthlyStats({ value, date_from: rangeStartMonth(range) });
  const months = monthlyStats.data ?? [];
  const series = selectStatistics(statistic);
  const isMonthInProgress = months.at(-1)?.is_partial ?? false;
  const change = statistic === "compare" ? null : changeOverCompleteMonths(months, statistic);
  const chartData = months as unknown as Record<string, unknown>[];

  return (
    <Card
      title="Patrimonio mes a mes"
      subtitle={STATISTIC_HINTS[statistic]}
      actions={<RangeSelector value={range} onChange={setRange} />}
    >
      <div className="filters" style={{ marginBottom: 12 }}>
        <Segmented options={STATISTIC_OPTIONS} value={statistic} onChange={setStatistic} label="Estadístico" />
        <Segmented options={NET_WORTH_VALUE_OPTIONS} value={value} onChange={setValue} label="Patrimonio" />
        {change && (
          <span className="secondary" style={{ fontSize: 13 }}>
            <Delta value={change.absolute} percent={change.relative} /> de {formatMonthTick(change.fromMonth)} a{" "}
            {formatMonthTick(change.toMonth)}
          </span>
        )}
      </div>

      {statistic === "compare" && <Legend items={series} />}
      {monthlyStats.error ? (
        <ErrorState error={monthlyStats.error} />
      ) : statistic === "compare" ? (
        <TimeLineChart data={chartData} series={series} xKey="month" formatLabel={formatMonthTick} />
      ) : (
        <MonthlyBarChart data={chartData} series={series} height={300} />
      )}

      {isMonthInProgress && (
        <p className="kpi-hint">
          El último mes está en curso ({months.at(-1)?.days} días): sus valores aún pueden cambiar.
          {statistic === "min_eur" && months.at(-1) && ` Mínimo hasta ahora: ${formatEur(months.at(-1)?.min_eur)}.`}
        </p>
      )}
    </Card>
  );
}
