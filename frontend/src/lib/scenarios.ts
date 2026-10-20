// Scenario editing for the Proyecciones page: defaults, form metadata,
// persistence and chart-ready data. Pure functions, unit-tested.

import type {
  InvestmentMode,
  InvestmentPlanStep,
  PercentilePoint,
  ProjectionPoint,
  SalaryStep,
  ScenarioParameters,
  ScenarioResult,
} from "../api/types";

export interface Scenario {
  id: string;
  name: string;
  parameters: ScenarioParameters;
}

// Plain numeric inputs of the form; salary calendar, pays and bonus month have their own editors
export type ParameterKey =
  | "start_cash_eur"
  | "start_investments_eur"
  | "salary_growth"
  | "monthly_other_income_eur"
  | "monthly_expenses_eur"
  | "inflation"
  | "monthly_investment_eur"
  | "investment_growth"
  | "cash_return"
  | "investment_return"
  | "investment_volatility";

export interface ParameterField {
  key: ParameterKey;
  label: string;
  unit: "eur" | "percent";
  hint?: string;
  // Shown only when the scenario invests a fixed amount
  onlyInFixedMode?: boolean;
}

export const PARAMETER_GROUPS: { title: string; fields: ParameterField[] }[] = [
  {
    title: "Punto de partida",
    fields: [
      { key: "start_cash_eur", label: "Efectivo inicial", unit: "eur" },
      { key: "start_investments_eur", label: "Inversiones iniciales", unit: "eur" },
    ],
  },
  {
    title: "Otros ingresos",
    fields: [
      { key: "salary_growth", label: "Subida salarial anual", unit: "percent", hint: "A partir del último cambio del calendario" },
      { key: "monthly_other_income_eur", label: "Otros ingresos al mes", unit: "eur", hint: "Bizums y similares" },
    ],
  },
  {
    title: "Gastos",
    fields: [
      { key: "monthly_expenses_eur", label: "Gasto mensual", unit: "eur" },
      { key: "inflation", label: "Inflación anual", unit: "percent", hint: "Sube los gastos y define los € de hoy" },
    ],
  },
  {
    title: "Inversión",
    fields: [
      { key: "monthly_investment_eur", label: "Aportación mensual", unit: "eur", onlyInFixedMode: true },
      { key: "investment_growth", label: "Aumento anual de la aportación", unit: "percent", onlyInFixedMode: true },
      { key: "investment_return", label: "Rentabilidad esperada", unit: "percent" },
      { key: "investment_volatility", label: "Volatilidad", unit: "percent", hint: "Anchura de la banda de incertidumbre" },
    ],
  },
  {
    title: "Efectivo",
    fields: [{ key: "cash_return", label: "Rentabilidad del efectivo", unit: "percent" }],
  },
];

export const HORIZON_OPTIONS: { key: string; label: string }[] = [
  { key: "5", label: "5 años" },
  { key: "10", label: "10 años" },
  { key: "20", label: "20 años" },
  { key: "30", label: "30 años" },
];

export const MAX_SCENARIOS = 4;
export const SCENARIO_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
// v2: the salary became a gross calendar converted to net (v1 scenarios are ignored)
const STORAGE_KEY = "fin_tracker.scenarios.v2";

export const MONTH_NAMES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

let scenarioCounter = 0;
/** Unique id for a new scenario (time + counter, stable within a session). */
export function newScenarioId(): string {
  scenarioCounter += 1;
  return `scenario-${Date.now()}-${scenarioCounter}`;
}

/** Three starting scenarios: my data as is, a better and a worse case. */
export function createDefaultScenarios(baseline: ScenarioParameters): Scenario[] {
  return [
    { id: newScenarioId(), name: "Base", parameters: { ...baseline } },
    {
      id: newScenarioId(),
      name: "Optimista",
      parameters: {
        ...baseline,
        salary_growth: baseline.salary_growth + 0.02,
        investment_return: baseline.investment_return + 0.015,
      },
    },
    {
      id: newScenarioId(),
      name: "Prudente",
      parameters: {
        ...baseline,
        salary_growth: 0.01,
        inflation: baseline.inflation + 0.005,
        investment_return: Math.max(0, baseline.investment_return - 0.025),
      },
    },
  ];
}

/** Copy of a scenario with a name not used by any other. */
export function duplicateScenario(scenario: Scenario, existing: Scenario[]): Scenario {
  const takenNames = new Set(existing.map((item) => item.name));
  let name = `${scenario.name} (copia)`;
  for (let copyNumber = 2; takenNames.has(name); copyNumber += 1) {
    name = `${scenario.name} (copia ${copyNumber})`;
  }
  return { id: newScenarioId(), name, parameters: { ...scenario.parameters } };
}

export function updateParameter(scenario: Scenario, key: ParameterKey, value: number): Scenario {
  return { ...scenario, parameters: { ...scenario.parameters, [key]: value } };
}

/** Value shown in the form: percents as 6.2 instead of 0.062, euros rounded. */
export function toInputValue(field: ParameterField, value: number): number {
  return field.unit === "percent" ? Math.round(value * 1000) / 10 : Math.round(value);
}

/** Inverse of ``toInputValue``; empty or invalid input counts as 0. */
export function fromInputValue(field: ParameterField, input: string): number {
  const value = Number(input.replace(",", "."));
  if (!Number.isFinite(value)) return 0;
  return field.unit === "percent" ? value / 100 : value;
}

/** Scenarios saved in this browser, or null (corrupt data or no storage counts as none). */
export function loadScenarios(storage: Pick<Storage, "getItem"> | undefined): Scenario[] | null {
  try {
    const stored = storage?.getItem(STORAGE_KEY);
    if (!stored) return null;
    const scenarios = JSON.parse(stored) as Scenario[];
    return Array.isArray(scenarios) && scenarios.length > 0 ? scenarios.map(withParameterDefaults) : null;
  } catch {
    return null;
  }
}

export function saveScenarios(storage: Pick<Storage, "setItem"> | undefined, scenarios: Scenario[]): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(scenarios));
  } catch {
    // Private mode or full storage: scenarios just won't survive a reload
  }
}

/** Divide a nominal value of month ``monthIndex`` (0-based) into today's euros. */
export function deflate(value: number, inflation: number, monthIndex: number): number {
  return value / (1 + inflation) ** ((monthIndex + 1) / 12);
}

/**
 * One chart row per month: every scenario's total under its name, plus the
 * active scenario's p10–p90 band.
 */
export function buildChartRows(
  results: ScenarioResult[],
  scenarios: Scenario[],
  activeName: string,
  inTodayEuros: boolean,
): Record<string, string | number | [number, number]>[] {
  const activeResult = results.find((result) => result.name === activeName);
  const activeInflation = scenarios.find((scenario) => scenario.name === activeName)?.parameters.inflation ?? 0;
  const months = results[0]?.points.map((point) => point.month) ?? [];

  return months.map((month, monthIndex) => {
    const row: Record<string, string | number | [number, number]> = { month };
    for (const result of results) {
      const point = result.points[monthIndex];
      if (point) row[result.name] = inTodayEuros ? point.total_real_eur : point.total_eur;
    }
    const percentile: PercentilePoint | undefined = activeResult?.percentiles[monthIndex];
    if (percentile) {
      const adjust = (value: number) => (inTodayEuros ? deflate(value, activeInflation, monthIndex) : value);
      row.band = [adjust(percentile.p10_eur), adjust(percentile.p90_eur)];
    }
    return row;
  });
}

/** Salary steps in date order. */
export function sortSalarySchedule(schedule: SalaryStep[]): SalaryStep[] {
  return [...schedule].sort((stepA, stepB) => stepA.start_month.localeCompare(stepB.start_month));
}

/** Month one year after ``month`` (YYYY-MM). */
export function addOneYear(month: string): string {
  return `${Number(month.slice(0, 4)) + 1}${month.slice(4)}`;
}

/** New salary change one year after the last one, starting from its amounts. */
export function addSalaryStep(scenario: Scenario, fallbackMonth: string): Scenario {
  const schedule = sortSalarySchedule(scenario.parameters.salary_schedule);
  const lastStep = schedule.at(-1);
  const newStep: SalaryStep = lastStep
    ? { ...lastStep, start_month: addOneYear(lastStep.start_month) }
    : { start_month: fallbackMonth, gross_salary_eur: 0, gross_bonus_eur: 0 };
  return { ...scenario, parameters: { ...scenario.parameters, salary_schedule: [...schedule, newStep] } };
}

export function updateSalaryStep(scenario: Scenario, index: number, patch: Partial<SalaryStep>): Scenario {
  const schedule = scenario.parameters.salary_schedule.map((step, stepIndex) =>
    stepIndex === index ? { ...step, ...patch } : step,
  );
  return { ...scenario, parameters: { ...scenario.parameters, salary_schedule: schedule } };
}

/** Remove a salary change; the calendar always keeps at least one step. */
export function removeSalaryStep(scenario: Scenario, index: number): Scenario {
  if (scenario.parameters.salary_schedule.length <= 1) return scenario;
  const schedule = scenario.parameters.salary_schedule.filter((_, stepIndex) => stepIndex !== index);
  return { ...scenario, parameters: { ...scenario.parameters, salary_schedule: schedule } };
}

export function updateSetting<K extends "payments_per_year" | "bonus_month" | "retention_rate_override">(
  scenario: Scenario,
  key: K,
  value: ScenarioParameters[K],
): Scenario {
  return { ...scenario, parameters: { ...scenario.parameters, [key]: value } };
}

/** Fill parameters added after a scenario was saved, so old scenarios keep working. */
export function withParameterDefaults(scenario: Scenario): Scenario {
  return {
    ...scenario,
    parameters: {
      ...scenario.parameters,
      investment_mode: scenario.parameters.investment_mode ?? "fixed",
      investment_plan: scenario.parameters.investment_plan ?? [],
    },
  };
}

export function setInvestmentMode(scenario: Scenario, mode: InvestmentMode): Scenario {
  return { ...scenario, parameters: { ...scenario.parameters, investment_mode: mode } };
}

/** Plan steps in year order. */
export function sortInvestmentPlan(plan: InvestmentPlanStep[]): InvestmentPlanStep[] {
  return [...plan].sort((stepA, stepB) => stepA.year - stepB.year);
}

/** New plan step the year after the last one (same share), or ``fallbackYear`` when empty. */
export function addPlanStep(scenario: Scenario, fallbackYear: number, fallbackPercent: number): Scenario {
  const plan = sortInvestmentPlan(scenario.parameters.investment_plan);
  const lastStep = plan.at(-1);
  const newStep: InvestmentPlanStep = lastStep
    ? { year: lastStep.year + 1, salary_percent: lastStep.salary_percent }
    : { year: fallbackYear, salary_percent: fallbackPercent };
  return { ...scenario, parameters: { ...scenario.parameters, investment_plan: [...plan, newStep] } };
}

export function updatePlanStep(scenario: Scenario, index: number, patch: Partial<InvestmentPlanStep>): Scenario {
  const plan = scenario.parameters.investment_plan.map((step, stepIndex) =>
    stepIndex === index ? { ...step, ...patch } : step,
  );
  return { ...scenario, parameters: { ...scenario.parameters, investment_plan: plan } };
}

/** Remove a plan step; at least one stays. */
export function removePlanStep(scenario: Scenario, index: number): Scenario {
  if (scenario.parameters.investment_plan.length <= 1) return scenario;
  const plan = scenario.parameters.investment_plan.filter((_, stepIndex) => stepIndex !== index);
  return { ...scenario, parameters: { ...scenario.parameters, investment_plan: plan } };
}

/** Money invested and net salary per calendar year of a projection. */
export function contributionsByYear(points: ProjectionPoint[]): Map<number, { investedEur: number; salaryEur: number }> {
  const byYear = new Map<number, { investedEur: number; salaryEur: number }>();
  for (const point of points) {
    const year = Number(point.month.slice(0, 4));
    const totals = byYear.get(year) ?? { investedEur: 0, salaryEur: 0 };
    totals.investedEur += point.contribution_eur;
    totals.salaryEur += point.salary_eur;
    byYear.set(year, totals);
  }
  return byYear;
}
