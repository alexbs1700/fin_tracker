// Time range presets shared by every chart filter

export type RangeKey = "3M" | "6M" | "1A" | "YTD" | "TODO";

export const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "3M", label: "3M" },
  { key: "6M", label: "6M" },
  { key: "YTD", label: "Año" },
  { key: "1A", label: "1A" },
  { key: "TODO", label: "Todo" },
];

const MONTHS_BACK: Partial<Record<RangeKey, number>> = { "3M": 3, "6M": 6, "1A": 12 };

/** ISO date (yyyy-mm-dd) of a local date, without timezone shifts. */
export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** First day of a range relative to ``today``, or undefined for the whole history. */
export function rangeStartDate(range: RangeKey, today: Date = new Date()): string | undefined {
  if (range === "TODO") return undefined;
  if (range === "YTD") return `${today.getFullYear()}-01-01`;
  const start = new Date(today);
  start.setMonth(start.getMonth() - (MONTHS_BACK[range] ?? 0));
  return toIsoDate(start);
}

/** Daily points for short ranges, weekly beyond six months to keep charts light. */
export function rangeFrequency(range: RangeKey): "D" | "W" {
  return range === "3M" || range === "6M" ? "D" : "W";
}

/** First date of every month in a sorted list, used as axis ticks so no month repeats. */
export function firstDatePerMonth(isoDates: string[]): string[] {
  const seenMonths = new Set<string>();
  return isoDates.filter((isoDate) => {
    const month = isoDate.slice(0, 7);
    if (seenMonths.has(month)) return false;
    seenMonths.add(month);
    return true;
  });
}

/** Start of a range moved back to the first day of its month, so months stay whole. */
export function rangeStartMonth(range: RangeKey, today: Date = new Date()): string | undefined {
  const startDate = rangeStartDate(range, today);
  return startDate ? `${startDate.slice(0, 7)}-01` : undefined;
}

/** The preset that produces exactly this period, or null for a custom one. */
export function matchingRange(
  dateFrom: string,
  dateTo: string,
  today: Date = new Date(),
): RangeKey | null {
  if (dateTo !== "") return null;
  const preset = RANGE_OPTIONS.find((option) => (rangeStartDate(option.key, today) ?? "") === dateFrom);
  return preset?.key ?? null;
}
