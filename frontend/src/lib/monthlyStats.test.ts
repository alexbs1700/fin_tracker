import { describe, expect, it } from "vitest";

import type { MonthlyNetWorthStats } from "../api/types";
import { changeOverCompleteMonths, selectStatistics, STATISTICS } from "./monthlyStats";

const month = (key: string, min: number, isPartial = false): MonthlyNetWorthStats => ({
  month: key,
  min_eur: min,
  max_eur: min + 10,
  mean_eur: min + 5,
  median_eur: min + 4,
  min_date: `${key}-01`,
  max_date: `${key}-02`,
  days: isPartial ? 10 : 30,
  is_partial: isPartial,
});

describe("selectStatistics", () => {
  it("returns one statistic or all four", () => {
    expect(selectStatistics("median_eur").map((statistic) => statistic.label)).toEqual(["Mediana"]);
    expect(selectStatistics("compare")).toEqual(STATISTICS);
  });
});

describe("changeOverCompleteMonths", () => {
  it("ignores the month in progress", () => {
    expect(
      changeOverCompleteMonths([month("2026-01", 100), month("2026-02", 150), month("2026-03", 999, true)], "min_eur"),
    ).toEqual({ absolute: 50, relative: 0.5, fromMonth: "2026-01", toMonth: "2026-02" });
  });

  it("needs two complete months", () => {
    expect(changeOverCompleteMonths([month("2026-01", 100), month("2026-02", 1, true)], "min_eur")).toBeNull();
  });
});
