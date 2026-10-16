import { describe, expect, it } from "vitest";

import type { LiquidityPoint, MonthlyCashFlow } from "../api/types";
import { computeChange, summarizeCashFlow } from "./metrics";

const point = (date: string, total: number): LiquidityPoint => ({
  date,
  cash_eur: total,
  investments_eur: 0,
  total_eur: total,
});

describe("computeChange", () => {
  it("returns absolute and relative change", () => {
    expect(computeChange([point("2026-01-01", 100), point("2026-02-01", 150)], "total_eur")).toEqual({
      absolute: 50,
      relative: 0.5,
    });
  });

  it("handles short series and a zero start", () => {
    expect(computeChange([point("2026-01-01", 100)], "total_eur")).toBeNull();
    expect(computeChange([point("2026-01-01", 0), point("2026-02-01", 5)], "total_eur")?.relative).toBeNull();
  });
});

describe("summarizeCashFlow", () => {
  const month = (income: number, expenses: number, invested: number): MonthlyCashFlow => ({
    month: "2026-01",
    income_eur: income,
    expenses_eur: expenses,
    savings_eur: income - expenses,
    savings_rate: null,
    invested_eur: invested,
  });

  it("adds months and computes the period savings rate", () => {
    expect(summarizeCashFlow([month(2000, 1500, 100), month(2000, 500, 300)])).toEqual({
      incomeEur: 4000,
      expensesEur: 2000,
      savingsEur: 2000,
      savingsRate: 0.5,
      investedEur: 400,
    });
  });

  it("has no savings rate without income", () => {
    expect(summarizeCashFlow([]).savingsRate).toBeNull();
  });
});
