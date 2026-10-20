// How a scenario invests: a fixed monthly amount, or a yearly plan of the
// share of each net payslip that goes to investments.

import type { InvestmentMode } from "../api/types";
import { formatPercent } from "../lib/format";
import {
  addPlanStep,
  removePlanStep,
  type Scenario,
  setInvestmentMode,
  updatePlanStep,
} from "../lib/scenarios";
import { Segmented } from "./ui";

const MODE_OPTIONS: { key: InvestmentMode; label: string }[] = [
  { key: "fixed", label: "Cantidad fija" },
  { key: "salary_percent", label: "% del salario" },
];

export function InvestmentPlanEditor({
  scenario,
  currentShare,
  firstYear,
  onChange,
}: {
  scenario: Scenario;
  currentShare: number | undefined;
  firstYear: number;
  onChange: (scenario: Scenario) => void;
}) {
  const { investment_mode: mode, investment_plan: plan } = scenario.parameters;

  return (
    <div style={{ marginBottom: 10 }}>
      <span className="form-label">Cómo inviertes</span>
      <Segmented
        options={MODE_OPTIONS}
        value={mode}
        onChange={(newMode) => {
          let updated = setInvestmentMode(scenario, newMode);
          // Switching to a plan for the first time starts from my current share
          if (newMode === "salary_percent" && plan.length === 0) {
            updated = addPlanStep(updated, firstYear, currentShare ?? 0.1);
          }
          onChange(updated);
        }}
        label="Modo de inversión"
      />

      {mode === "salary_percent" && (
        <>
          <p className="kpi-hint">Porcentaje de cada nómina neta (incluye pagas extra y bonus) desde el año indicado.</p>
          <div className="salary-steps" style={{ marginTop: 8 }}>
            <div className="plan-step salary-step-header">
              <span>Desde el año</span>
              <span>% del neto</span>
              <span />
            </div>
            {plan.map((step, index) => (
              <div key={index} className="plan-step">
                <input
                  type="number"
                  aria-label="Desde el año"
                  min={2000}
                  max={2100}
                  value={step.year}
                  onChange={(event) =>
                    onChange(updatePlanStep(scenario, index, { year: Number(event.target.value) || firstYear }))
                  }
                />
                <div className="input-with-unit">
                  <input
                    type="number"
                    aria-label="Porcentaje del salario neto"
                    min={0}
                    max={100}
                    step={1}
                    value={Math.round(step.salary_percent * 1000) / 10}
                    onChange={(event) =>
                      onChange(
                        updatePlanStep(scenario, index, {
                          salary_percent: Math.min(1, Math.max(0, (Number(event.target.value) || 0) / 100)),
                        }),
                      )
                    }
                  />
                  <span className="unit">%</span>
                </div>
                <button
                  type="button"
                  className="link-button"
                  aria-label="Quitar año"
                  disabled={plan.length <= 1}
                  onClick={() => onChange(removePlanStep(scenario, index))}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className="link-button"
            onClick={() => onChange(addPlanStep(scenario, firstYear, currentShare ?? 0.1))}
          >
            + Añadir año
          </button>
          {currentShare !== undefined && (
            <p className="kpi-hint">Tus datos: inviertes ≈{formatPercent(currentShare)} de tu nómina neta.</p>
          )}
        </>
      )}
    </div>
  );
}
