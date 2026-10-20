// Proyecciones: compare editable scenarios of how my net worth could evolve.
// Defaults come from my own data; scenarios are saved in this browser.

import { useEffect, useMemo, useState } from "react";

import { useProjectionBaseline, useSimulation } from "../api/client";
import type { ScenarioParameters, ScenarioResult } from "../api/types";
import { ProjectionChart, StackedAreaChart, type SeriesSpec } from "../components/charts";
import { InvestmentPlanEditor } from "../components/InvestmentPlanEditor";
import { PayrollTable, SalaryEditor } from "../components/SalaryEditor";
import { Card, ErrorState, Legend, LoadingState, Segmented } from "../components/ui";
import { formatEur, formatMonthTick, formatPercent } from "../lib/format";
import {
  buildChartRows,
  contributionsByYear,
  createDefaultScenarios,
  duplicateScenario,
  fromInputValue,
  HORIZON_OPTIONS,
  loadScenarios,
  MAX_SCENARIOS,
  PARAMETER_GROUPS,
  type ParameterField,
  type Scenario,
  SCENARIO_COLORS,
  saveScenarios,
  toInputValue,
  updateParameter,
} from "../lib/scenarios";

type ValueMode = "nominal" | "real";
const VALUE_MODE_OPTIONS: { key: ValueMode; label: string }[] = [
  { key: "nominal", label: "€ nominales" },
  { key: "real", label: "€ de hoy" },
];

const COMPOSITION_SERIES: SeriesSpec[] = [
  { key: "cash_eur", label: "Efectivo", color: "var(--series-1)" },
  { key: "investments_eur", label: "Inversiones", color: "var(--series-2)" },
];

function getStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

export default function Projections() {
  const baseline = useProjectionBaseline();
  const [scenarios, setScenarios] = useState<Scenario[]>(() => loadScenarios(getStorage()) ?? []);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [horizon, setHorizon] = useState("10");
  const [valueMode, setValueMode] = useState<ValueMode>("nominal");

  // First visit: seed the scenarios from my data once the baseline arrives
  useEffect(() => {
    if (scenarios.length === 0 && baseline.data) setScenarios(createDefaultScenarios(baseline.data));
  }, [baseline.data, scenarios.length]);
  useEffect(() => saveScenarios(getStorage(), scenarios), [scenarios]);

  const activeScenario = scenarios.find((scenario) => scenario.id === activeId) ?? scenarios[0];
  const requestScenarios = useMemo(
    () =>
      scenarios.map((scenario) => ({
        name: scenario.name,
        parameters: { ...scenario.parameters, horizon_years: Number(horizon) },
      })),
    [scenarios, horizon],
  );
  const simulation = useSimulation(requestScenarios);

  if (baseline.isLoading || !activeScenario) return <LoadingState />;
  if (baseline.error) return <ErrorState error={baseline.error} />;

  const results = simulation.data ?? [];
  const activeResult = results.find((result) => result.name === activeScenario.name);
  const activeIndex = scenarios.indexOf(activeScenario);
  const series: SeriesSpec[] = scenarios.map((scenario, index) => ({
    key: scenario.name,
    label: scenario.name,
    color: SCENARIO_COLORS[index],
  }));
  const chartRows = buildChartRows(results, scenarios, activeScenario.name, valueMode === "real");
  const lastBand = chartRows.at(-1)?.band as [number, number] | undefined;

  const replaceActive = (updated: Scenario) =>
    setScenarios(scenarios.map((scenario) => (scenario.id === updated.id ? updated : scenario)));

  const renameActive = (name: string) => {
    // Names identify results, so they must stay unique and non-empty
    const isTaken = scenarios.some((scenario) => scenario.id !== activeScenario.id && scenario.name === name);
    if (name.trim() && !isTaken) replaceActive({ ...activeScenario, name });
  };

  return (
    <>
      <p className="page-title">
        Patrimonio estimado en {horizon} años · escenario {activeScenario.name}
      </p>
      <div className="hero-row">
        <h1 className="hero-value">
          {formatEur(
            valueMode === "real" ? activeResult?.summary.final_total_real_eur : activeResult?.summary.final_total_eur,
          )}
        </h1>
        {activeResult && (
          <span className="muted">
            {valueMode === "nominal"
              ? `≈ ${formatEur(activeResult.summary.final_total_real_eur)} de hoy`
              : `${formatEur(activeResult.summary.final_total_eur)} nominales`}
            {lastBand && ` · 80 % de los casos entre ${formatEur(lastBand[0])} y ${formatEur(lastBand[1])}`}
          </span>
        )}
      </div>

      <div className="filters">
        <Segmented options={HORIZON_OPTIONS} value={horizon} onChange={setHorizon} label="Horizonte" />
        <Segmented options={VALUE_MODE_OPTIONS} value={valueMode} onChange={setValueMode} label="Valores" />
      </div>

      <div className="filters" role="group" aria-label="Escenarios">
        {scenarios.map((scenario, index) => (
          <button
            key={scenario.id}
            type="button"
            className={`chip${scenario.id === activeScenario.id ? " active" : ""}`}
            aria-pressed={scenario.id === activeScenario.id}
            onClick={() => setActiveId(scenario.id)}
          >
            <span className="legend-swatch" style={{ background: SCENARIO_COLORS[index], display: "inline-block", marginRight: 6 }} />
            {scenario.name}
          </button>
        ))}
        <button
          type="button"
          className="chip"
          disabled={scenarios.length >= MAX_SCENARIOS}
          title={scenarios.length >= MAX_SCENARIOS ? `Máximo ${MAX_SCENARIOS} escenarios` : "Copia el escenario seleccionado"}
          onClick={() => {
            const copy = duplicateScenario(activeScenario, scenarios);
            setScenarios([...scenarios, copy]);
            setActiveId(copy.id);
          }}
        >
          + Duplicar
        </button>
        {baseline.data && (
          <button
            type="button"
            className="chip"
            title="Vuelve a los tres escenarios calculados con tus datos actuales"
            onClick={() => {
              const defaults = createDefaultScenarios(baseline.data);
              setScenarios(defaults);
              setActiveId(defaults[0].id);
            }}
          >
            ↺ Restablecer con mis datos
          </button>
        )}
      </div>

      <div className="projection-layout">
        <Card title="Parámetros" subtitle="Tasas anuales · se aplican al escenario seleccionado">
          <div className="form-row">
            <label className="form-field">
              <span>Nombre</span>
              <input type="text" defaultValue={activeScenario.name} key={activeScenario.id} onBlur={(event) => renameActive(event.target.value)} />
            </label>
          </div>
          <SalaryEditor
            scenario={activeScenario}
            baselineStep={baseline.data?.salary_schedule[0]}
            firstMonth={results[0]?.points[0]?.month ?? new Date().toISOString().slice(0, 7)}
            onChange={replaceActive}
          />
          {PARAMETER_GROUPS.map((group) => (
            <fieldset key={group.title} className="form-group">
              <legend>{group.title}</legend>
              {group.title === "Inversión" && (
                <InvestmentPlanEditor
                  scenario={activeScenario}
                  currentShare={baseline.data?.investment_plan[0]?.salary_percent}
                  firstYear={Number((results[0]?.points[0]?.month ?? String(new Date().getFullYear())).slice(0, 4))}
                  onChange={replaceActive}
                />
              )}
              {group.fields
                .filter((field) => !(field.onlyInFixedMode && activeScenario.parameters.investment_mode !== "fixed"))
                .map((field) => (
                <ParameterInput
                  key={`${activeScenario.id}-${field.key}`}
                  field={field}
                  value={activeScenario.parameters[field.key]}
                  baselineValue={baseline.data?.[field.key]}
                  onChange={(value) => replaceActive(updateParameter(activeScenario, field.key, value))}
                />
              ))}
            </fieldset>
          ))}
          <button
            className="button"
            disabled={scenarios.length <= 1}
            onClick={() => {
              setScenarios(scenarios.filter((scenario) => scenario.id !== activeScenario.id));
              setActiveId(null);
            }}
          >
            Eliminar escenario
          </button>
        </Card>

        <div className="stack">
          <Card
            title="Patrimonio total por escenario"
            subtitle={`La banda es el rango del 80 % de ${activeScenario.name} según la volatilidad`}
          >
            <Legend items={series} />
            {simulation.error ? (
              <ErrorState error={simulation.error} />
            ) : (
              <ProjectionChart
                data={chartRows as unknown as Record<string, unknown>[]}
                series={series}
                activeKey={activeScenario.name}
                activeColor={SCENARIO_COLORS[activeIndex]}
              />
            )}
          </Card>

          <Card title={`Composición · ${activeScenario.name}`} subtitle="Efectivo e inversiones apilados, en € nominales">
            <Legend items={COMPOSITION_SERIES} />
            <StackedAreaChart
              data={(activeResult?.points ?? []) as unknown as Record<string, unknown>[]}
              series={COMPOSITION_SERIES}
              xKey="month"
              formatLabel={formatMonthTick}
              height={240}
            />
          </Card>

          <Card title={`Comparativa a ${horizon} años`}>
            <ScenarioComparison results={results} scenarios={scenarios} />
          </Card>

          <Card
            title={`Nómina estimada · ${activeScenario.name}`}
            subtitle="Seguridad Social 6,5 %, retención de IRPF según la escala estatal y renta con la escala de Madrid"
          >
            <PayrollTable
              payrollYears={activeResult?.payroll_years ?? []}
              contributionsByYear={contributionsByYear(activeResult?.points ?? [])}
              paymentsPerYear={activeScenario.parameters.payments_per_year}
            />
          </Card>
        </div>
      </div>
    </>
  );
}

function ParameterInput({
  field,
  value,
  baselineValue,
  onChange,
}: {
  field: ParameterField;
  value: number;
  baselineValue: number | undefined;
  onChange: (value: number) => void;
}) {
  const formattedBaseline =
    baselineValue === undefined
      ? null
      : field.unit === "percent"
        ? formatPercent(baselineValue)
        : formatEur(baselineValue);
  const isAtBaseline = baselineValue !== undefined && Math.abs(baselineValue - value) < 1e-9;
  // Local text so typing "6," is not overwritten; resync when the value changes from outside
  const [text, setText] = useState(String(toInputValue(field, value)));
  useEffect(() => {
    if (fromInputValue(field, text) !== value) setText(String(toInputValue(field, value)));
  }, [value]);

  return (
    <label className="form-field">
      <span>
        {field.label}
        {field.hint && <span className="muted"> · {field.hint}</span>}
      </span>
      <div className="input-with-unit">
        <input
          type="number"
          step={field.unit === "percent" ? 0.1 : 10}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            onChange(fromInputValue(field, event.target.value));
          }}
        />
        <span className="unit">{field.unit === "percent" ? "%" : "€"}</span>
      </div>
      {formattedBaseline && !isAtBaseline && (
        <button type="button" className="link-button" onClick={() => onChange(baselineValue!)}>
          Tus datos: {formattedBaseline} · usar
        </button>
      )}
    </label>
  );
}

function ScenarioComparison({ results, scenarios }: { results: ScenarioResult[]; scenarios: Scenario[] }) {
  if (results.length === 0) return <LoadingState />;
  const parametersByName = new Map<string, ScenarioParameters>(
    scenarios.map((scenario) => [scenario.name, scenario.parameters]),
  );
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Escenario</th>
            <th className="num">Patrimonio</th>
            <th className="num">En € de hoy</th>
            <th className="num">Aportado</th>
            <th className="num">Ganado invirtiendo</th>
            <th className="num">Efectivo final</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result, index) => (
            <tr key={result.name}>
              <td>
                <span className="legend-swatch" style={{ background: SCENARIO_COLORS[index], display: "inline-block", marginRight: 8 }} />
                {result.name}
                <div className="muted" style={{ fontSize: 11 }}>
                  {formatPercent(parametersByName.get(result.name)?.investment_return)} rent. ·{" "}
                  {formatEur(parametersByName.get(result.name)?.monthly_investment_eur)}/mes
                </div>
              </td>
              <td className="num">{formatEur(result.summary.final_total_eur)}</td>
              <td className="num secondary">{formatEur(result.summary.final_total_real_eur)}</td>
              <td className="num secondary">{formatEur(result.summary.total_contributions_eur)}</td>
              <td className="num">{formatEur(result.summary.investment_gains_eur)}</td>
              <td className="num">
                {formatEur(result.summary.final_cash_eur)}
                {result.summary.first_negative_cash_month && (
                  <div className="status-text critical" style={{ fontSize: 11, margin: 0 }}>
                    ⚠ En negativo desde {formatMonthTick(result.summary.first_negative_cash_month)}
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
