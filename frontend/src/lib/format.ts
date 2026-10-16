// Spanish (es-ES) formatting for money, percentages and dates

const EUR_FORMAT = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const EUR_COMPACT_FORMAT = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 1,
});

const PERCENT_FORMAT = new Intl.NumberFormat("es-ES", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const MONTH_NAMES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** 1234.5 -> "1234,50 €"; missing values render as an em dash. */
export function formatEur(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : EUR_FORMAT.format(value);
}

/** Axis-friendly money: 12500 -> "12,5 mil €". */
export function formatEurCompact(value: number): string {
  return EUR_COMPACT_FORMAT.format(value);
}

/** Money with an explicit sign, for gains and changes: +12,00 € / −3,00 €. */
export function formatSignedEur(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${EUR_FORMAT.format(Math.abs(value))}`;
}

/** 0.0532 -> "+5,3 %" (sign shown) or "5,3 %". */
export function formatPercent(value: number | null | undefined, withSign = false): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const formatted = PERCENT_FORMAT.format(Math.abs(value));
  if (!withSign) return value < 0 ? `−${formatted}` : formatted;
  return `${value > 0 ? "+" : value < 0 ? "−" : ""}${formatted}`;
}

/** "2026-10-15" -> "15 oct 2026". */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return `${Number(day)} ${MONTH_NAMES[Number(month) - 1]} ${year}`;
}

/** "2026-10-15" or "2026-10" -> "oct 26", for compact time axes. */
export function formatMonthTick(isoDate: string): string {
  const [year, month] = isoDate.split("-");
  return `${MONTH_NAMES[Number(month) - 1]} ${year.slice(2)}`;
}
