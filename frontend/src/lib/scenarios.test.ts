import { describe, expect, it } from "vitest";

import type { ScenarioParameters, ScenarioResult } from "../api/types";
import {
  addOneYear,
  addSalaryStep,
  buildChartRows,
  createDefaultScenarios,
  deflate,
  duplicateScenario,
  fromInputValue,
  loadScenarios,
  newScenarioId,
  PARAMETER_GROUPS,
  removeSalaryStep,
  saveScenarios,
  sortSalarySchedule,
  toInputValue,
  updateParameter,
  updateSalaryStep,
  updateSetting,
} from "./scenarios";

const BASELINE: ScenarioParameters = {
  horizon_years: 10,
  start_cash_eur: 1000,
  start_investments_eur: 500,
  salary_schedule: [{ start_month: "2026-09", gross_salary_eur: 35400, gross_bonus_eur: 3000 }],
  salary_growth: 0.03,
  payments_per_year: 14,
  bonus_month: 7,
  retention_rate_override: null,
  monthly_other_income_eur: 0,
  monthly_expenses_eur: 1500,
  inflation: 0.025,
  monthly_investment_eur: 200,
  investment_growth: 0,
  cash_return: 0.01,
  investment_return: 0.06,
  investment_volatility: 0.15,
};

const PERCENT_FIELD = { key: "salary_growth" as const, label: "x", unit: "percent" as const };
const EUR_FIELD = { key: "start_cash_eur" as const, label: "x", unit: "eur" as const };

describe("scenarios", () => {
  it("newScenarioId is unique", () => {
    expect(newScenarioId()).not.toBe(newScenarioId());
  });

  it("createDefaultScenarios derives better and worse cases", () => {
    const [base, optimistic, prudent] = createDefaultScenarios(BASELINE);
    expect(base.parameters).toEqual(BASELINE);
    expect(optimistic.parameters.investment_return).toBeCloseTo(0.075);
    expect(prudent.parameters.investment_return).toBeCloseTo(0.035);
    expect(prudent.parameters.salary_growth).toBe(0.01);
  });

  it("duplicateScenario finds a free name", () => {
    const [base] = createDefaultScenarios(BASELINE);
    const copy = duplicateScenario(base, [base]);
    expect(copy.name).toBe("Base (copia)");
    expect(duplicateScenario(base, [base, copy]).name).toBe("Base (copia 2)");
    expect(copy.id).not.toBe(base.id);
  });

  it("updateParameter does not mutate", () => {
    const [base] = createDefaultScenarios(BASELINE);
    const updated = updateParameter(base, "monthly_investment_eur", 500);
    expect(updated.parameters.monthly_investment_eur).toBe(500);
    expect(base.parameters.monthly_investment_eur).toBe(200);
  });

  it("converts form values", () => {
    expect(toInputValue(PERCENT_FIELD, 0.0622)).toBe(6.2);
    expect(toInputValue(EUR_FIELD, 1919.5)).toBe(1920);
    expect(fromInputValue(PERCENT_FIELD, "6,5")).toBeCloseTo(0.065);
    expect(fromInputValue(EUR_FIELD, "abc")).toBe(0);
  });

  it("every form field is a real parameter", () => {
    const keys = PARAMETER_GROUPS.flatMap((group) => group.fields.map((field) => field.key));
    for (const key of keys) expect(BASELINE).toHaveProperty(key);
  });

  it("persists scenarios and survives broken storage", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (key: string) => store.get(key) ?? null, setItem: (key: string, value: string) => void store.set(key, value) };
    const scenarios = createDefaultScenarios(BASELINE);
    saveScenarios(storage, scenarios);
    expect(loadScenarios(storage)).toEqual(scenarios);

    expect(loadScenarios({ getItem: () => "{not json" })).toBeNull();
    expect(loadScenarios({ getItem: () => "[]" })).toBeNull();
    expect(loadScenarios(undefined)).toBeNull();
    expect(() => saveScenarios({ setItem: () => { throw new Error("full"); } }, scenarios)).not.toThrow();
  });

  it("deflate", () => {
    expect(deflate(1050, 0.05, 11)).toBeCloseTo(1000);
  });

  it("buildChartRows puts every scenario and the active band on each month", () => {
    const result = (name: string, total: number): ScenarioResult => ({
      name,
      summary: {} as ScenarioResult["summary"],
      payroll_years: [],
      points: [{ month: "2027-01", total_eur: total, total_real_eur: total / 2 } as ScenarioResult["points"][0]],
      percentiles: [{ month: "2027-01", p10_eur: total - 10, p50_eur: total, p90_eur: total + 10 }],
    });
    const scenarios = createDefaultScenarios({ ...BASELINE, inflation: 0 }).slice(0, 2);
    const rows = buildChartRows([result("Base", 100), result("Optimista", 200)], scenarios, "Optimista", false);
    expect(rows).toEqual([{ month: "2027-01", Base: 100, Optimista: 200, band: [190, 210] }]);
    expect(buildChartRows([result("Base", 100)], scenarios, "Base", true)[0].Base).toBe(50);
  });
});

describe("salary calendar", () => {
  const [base] = createDefaultScenarios(BASELINE);

  it("adds a change one year after the last one", () => {
    expect(addOneYear("2026-09")).toBe("2027-09");
    const withStep = addSalaryStep(base, "2026-11");
    expect(withStep.parameters.salary_schedule.at(-1)).toEqual({
      start_month: "2027-09",
      gross_salary_eur: 35400,
      gross_bonus_eur: 3000,
    });
    const empty = { ...base, parameters: { ...base.parameters, salary_schedule: [] } };
    expect(addSalaryStep(empty, "2026-11").parameters.salary_schedule[0].start_month).toBe("2026-11");
  });

  it("updates, sorts and removes steps, keeping at least one", () => {
    const updated = updateSalaryStep(addSalaryStep(base, "x"), 1, { start_month: "2026-01", gross_salary_eur: 30000 });
    expect(sortSalarySchedule(updated.parameters.salary_schedule).map((step) => step.start_month)).toEqual([
      "2026-01",
      "2026-09",
    ]);
    expect(removeSalaryStep(updated, 0).parameters.salary_schedule).toHaveLength(1);
    expect(removeSalaryStep(base, 0)).toBe(base);
  });

  it("updates pays, bonus month and the withholding override", () => {
    expect(updateSetting(base, "payments_per_year", 12).parameters.payments_per_year).toBe(12);
    expect(updateSetting(base, "retention_rate_override", 0.18).parameters.retention_rate_override).toBe(0.18);
  });
});
