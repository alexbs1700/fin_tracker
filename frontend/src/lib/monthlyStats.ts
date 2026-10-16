// Options of the monthly net worth statistics chart

import type { MonthlyNetWorthStats } from "../api/types";

export type StatisticKey = "min_eur" | "max_eur" | "mean_eur" | "median_eur";
export type StatisticSelection = StatisticKey | "compare";
export type NetWorthValue = "total" | "cash" | "investments";

// Each statistic keeps its own validated series slot, in single and compare mode alike
export const STATISTICS: { key: StatisticKey; label: string; color: string }[] = [
  { key: "min_eur", label: "Mínimo", color: "var(--series-1)" },
  { key: "max_eur", label: "Máximo", color: "var(--series-2)" },
  { key: "mean_eur", label: "Media", color: "var(--series-3)" },
  { key: "median_eur", label: "Mediana", color: "var(--series-4)" },
];

export const STATISTIC_OPTIONS: { key: StatisticSelection; label: string }[] = [
  ...STATISTICS.map(({ key, label }) => ({ key, label })),
  { key: "compare", label: "Comparar" },
];

export const NET_WORTH_VALUE_OPTIONS: { key: NetWorthValue; label: string }[] = [
  { key: "total", label: "Total" },
  { key: "cash", label: "Líquido" },
  { key: "investments", label: "Inversión" },
];

/** Statistics drawn for a selection: the chosen one, or all four to compare. */
export function selectStatistics(selection: StatisticSelection) {
  return selection === "compare"
    ? STATISTICS
    : STATISTICS.filter((statistic) => statistic.key === selection);
}

/** Change of a statistic between the first and last complete months, if any. */
export function changeOverCompleteMonths(
  months: MonthlyNetWorthStats[],
  statistic: StatisticKey,
): { absolute: number; relative: number | null; fromMonth: string; toMonth: string } | null {
  const completeMonths = months.filter((month) => !month.is_partial);
  if (completeMonths.length < 2) return null;
  const first = completeMonths[0];
  const last = completeMonths[completeMonths.length - 1];
  const absolute = last[statistic] - first[statistic];
  return {
    absolute,
    relative: first[statistic] !== 0 ? absolute / Math.abs(first[statistic]) : null,
    fromMonth: first.month,
    toMonth: last.month,
  };
}
