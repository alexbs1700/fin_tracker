// Small derived numbers shown in the UI, kept pure so they are unit-tested

import type { LiquidityPoint, MonthlyCashFlow } from "../api/types";

/** Change between the first and last point of a series, absolute and relative. */
export function computeChange(
  points: LiquidityPoint[],
  field: keyof Omit<LiquidityPoint, "date">,
): { absolute: number; relative: number | null } | null {
  if (points.length < 2) return null;
  const first = points[0][field];
  const last = points[points.length - 1][field];
  return { absolute: last - first, relative: first !== 0 ? (last - first) / Math.abs(first) : null };
}

/** Totals over several months, with the savings rate of the whole period. */
export function summarizeCashFlow(months: MonthlyCashFlow[]): {
  incomeEur: number;
  expensesEur: number;
  savingsEur: number;
  savingsRate: number | null;
  investedEur: number;
} {
  const incomeEur = months.reduce((total, month) => total + month.income_eur, 0);
  const expensesEur = months.reduce((total, month) => total + month.expenses_eur, 0);
  const investedEur = months.reduce((total, month) => total + month.invested_eur, 0);
  const savingsEur = incomeEur - expensesEur;
  return {
    incomeEur,
    expensesEur,
    savingsEur,
    savingsRate: incomeEur > 0 ? savingsEur / incomeEur : null,
    investedEur,
  };
}
