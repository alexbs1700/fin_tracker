// Small presentational building blocks shared by every page

import type { ReactNode } from "react";

import { formatPercent, formatSignedEur } from "../lib/format";
import { RANGE_OPTIONS, type RangeKey } from "../lib/ranges";

export function Card({
  title,
  subtitle,
  actions,
  children,
}: {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <header className="card-header">
          <div>
            {title && <h2 className="card-title">{title}</h2>}
            {subtitle && <p className="card-subtitle">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

/** Signed change with an arrow, so gains and losses never rely on color alone. */
export function Delta({ value, percent }: { value?: number | null; percent?: number | null }) {
  const reference = value ?? percent ?? 0;
  const tone = reference > 0 ? "positive" : reference < 0 ? "negative" : "neutral";
  const arrow = reference > 0 ? "▲" : reference < 0 ? "▼" : "■";
  return (
    <span className={`delta ${tone}`}>
      {arrow} {value !== undefined && value !== null && formatSignedEur(value)}
      {percent !== undefined && percent !== null && ` (${formatPercent(percent, true)})`}
    </span>
  );
}

export function KpiTile({
  label,
  value,
  hint,
  delta,
}: {
  label: string;
  value: string;
  hint?: ReactNode;
  delta?: ReactNode;
}) {
  return (
    <div className="card">
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{value}</p>
      {delta && <div style={{ marginTop: 6 }}>{delta}</div>}
      {hint && <p className="kpi-hint">{hint}</p>}
    </div>
  );
}

/** Pill-shaped single choice control. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { key: T; label: string }[];
  value: T | null;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          className={option.key === value ? "active" : ""}
          aria-pressed={option.key === value}
          onClick={() => onChange(option.key)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function RangeSelector({
  value,
  onChange,
}: {
  value: RangeKey | null;
  onChange: (range: RangeKey) => void;
}) {
  return <Segmented options={RANGE_OPTIONS} value={value} onChange={onChange} label="Periodo" />;
}

export function Legend({
  items,
}: {
  items: { label: string; color: string; dashed?: boolean }[];
}) {
  return (
    <div className="legend">
      {items.map((item) => (
        <span key={item.label} className="legend-item">
          <span
            className={`legend-swatch${item.dashed ? " dashed" : ""}`}
            style={item.dashed ? undefined : { background: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function LoadingState() {
  return <p className="state">Cargando…</p>;
}

export function ErrorState({ error }: { error: unknown }) {
  return (
    <p className="state error">
      No se pudo cargar: {error instanceof Error ? error.message : String(error)}. ¿Está
      la API levantada (<code>uv run fin-tracker-api</code>)?
    </p>
  );
}
