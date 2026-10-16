// Salary inputs of a scenario: gross salary calendar, number of pays, bonus
// month and an optional fixed IRPF withholding rate; plus the yearly payroll.

import type { PayrollYear, SalaryStep, ScenarioParameters } from "../api/types";
import { formatEur, formatMonthTick, formatPercent } from "../lib/format";
import {
  addSalaryStep,
  MONTH_NAMES,
  removeSalaryStep,
  type Scenario,
  updateSalaryStep,
  updateSetting,
} from "../lib/scenarios";

export function SalaryEditor({
  scenario,
  baselineStep,
  firstMonth,
  onChange,
}: {
  scenario: Scenario;
  baselineStep: SalaryStep | undefined;
  firstMonth: string;
  onChange: (scenario: Scenario) => void;
}) {
  const parameters: ScenarioParameters = scenario.parameters;
  const isOverridingRetention = parameters.retention_rate_override !== null;

  return (
    <fieldset className="form-group">
      <legend>Salario (bruto → neto)</legend>

      <label className="form-field">
        <span>Pagas</span>
        <select
          value={parameters.payments_per_year}
          onChange={(event) => onChange(updateSetting(scenario, "payments_per_year", Number(event.target.value) as 12 | 14))}
        >
          <option value={14}>14 pagas (extras en julio y diciembre)</option>
          <option value={12}>12 pagas (extras prorrateadas)</option>
        </select>
      </label>

      <span className="form-label">Calendario salarial · bruto anual</span>
      <div className="salary-steps">
        <div className="salary-step salary-step-header">
          <span>Desde</span>
          <span>Fijo</span>
          <span>Bonus</span>
          <span />
        </div>
        {parameters.salary_schedule.map((step, index) => (
          <div key={index} className="salary-step">
            <input
              type="month"
              aria-label="Desde"
              value={step.start_month}
              onChange={(event) =>
                event.target.value && onChange(updateSalaryStep(scenario, index, { start_month: event.target.value }))
              }
            />
            <input
              type="number"
              aria-label="Bruto fijo anual"
              step={500}
              value={Math.round(step.gross_salary_eur)}
              onChange={(event) =>
                onChange(updateSalaryStep(scenario, index, { gross_salary_eur: Number(event.target.value) || 0 }))
              }
            />
            <input
              type="number"
              aria-label="Bonus anual bruto"
              step={500}
              value={Math.round(step.gross_bonus_eur)}
              onChange={(event) =>
                onChange(updateSalaryStep(scenario, index, { gross_bonus_eur: Number(event.target.value) || 0 }))
              }
            />
            <button
              type="button"
              className="link-button"
              aria-label="Quitar cambio salarial"
              disabled={parameters.salary_schedule.length <= 1}
              onClick={() => onChange(removeSalaryStep(scenario, index))}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <button type="button" className="link-button" onClick={() => onChange(addSalaryStep(scenario, firstMonth))}>
        + Añadir cambio salarial
      </button>
      {baselineStep && (
        <p className="kpi-hint">
          Estimado de tu última nómina: {formatEur(baselineStep.gross_salary_eur)} fijos ({formatMonthTick(baselineStep.start_month)})
        </p>
      )}

      <label className="form-field" style={{ marginTop: 10 }}>
        <span>Mes del bonus</span>
        <select
          value={parameters.bonus_month}
          onChange={(event) => onChange(updateSetting(scenario, "bonus_month", Number(event.target.value)))}
        >
          {MONTH_NAMES.map((name, index) => (
            <option key={name} value={index + 1}>{name}</option>
          ))}
        </select>
      </label>

      <label className="form-field checkbox-field">
        <input
          type="checkbox"
          checked={isOverridingRetention}
          onChange={(event) =>
            onChange(updateSetting(scenario, "retention_rate_override", event.target.checked ? 0.18 : null))
          }
        />
        <span>Fijar el tipo de retención de IRPF (si no, se calcula)</span>
      </label>
      {isOverridingRetention && (
        <div className="input-with-unit">
          <input
            type="number"
            step={0.1}
            aria-label="Tipo de retención"
            value={Math.round((parameters.retention_rate_override ?? 0) * 1000) / 10}
            onChange={(event) =>
              onChange(updateSetting(scenario, "retention_rate_override", (Number(event.target.value) || 0) / 100))
            }
          />
          <span className="unit">%</span>
        </div>
      )}
    </fieldset>
  );
}

/** Year by year: gross, payslips, withholding and the refund settled next June. */
export function PayrollTable({ payrollYears, paymentsPerYear }: { payrollYears: PayrollYear[]; paymentsPerYear: number }) {
  if (payrollYears.length === 0) return <p className="muted">Sin salario en este escenario.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Año</th>
            <th className="num">Bruto</th>
            <th className="num">Nómina mensual</th>
            {paymentsPerYear === 14 && <th className="num">Paga extra</th>}
            <th className="num">Bonus neto</th>
            <th className="num">Retención</th>
            <th className="num">Neto del año</th>
            <th className="num">Renta (junio siguiente)</th>
          </tr>
        </thead>
        <tbody>
          {payrollYears.map((year) => (
            <tr key={year.year}>
              <td>{year.year}</td>
              <td className="num secondary">{formatEur(year.gross_eur)}</td>
              <td className="num">{formatEur(year.regular_month_net_eur)}</td>
              {paymentsPerYear === 14 && <td className="num">{formatEur(year.extra_pay_net_eur)}</td>}
              <td className="num">{formatEur(year.bonus_net_eur)}</td>
              <td className="num secondary">{formatPercent(year.retention_rate)}</td>
              <td className="num">{formatEur(year.net_eur)}</td>
              <td className="num">
                <span className={`delta ${year.refund_eur >= 0 ? "positive" : "negative"}`}>
                  {year.refund_eur >= 0 ? "▲ a devolver" : "▼ a pagar"} {formatEur(Math.abs(year.refund_eur))}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
