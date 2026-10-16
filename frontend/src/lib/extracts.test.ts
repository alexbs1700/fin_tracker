import { describe, expect, it } from "vitest";

import type { ExtractReport } from "../api/types";
import { describeSummary, replaceButtonLabel, rowDifference } from "./extracts";

const summary = (rows: number) => ({
  rows,
  date_from: "2025-01-14",
  date_to: "2026-10-13",
  sub_accounts: [],
});

const report = (overrides: Partial<ExtractReport> = {}): ExtractReport => ({
  bank: "bbva",
  is_valid: true,
  errors: [],
  warnings: [],
  summary: summary(10),
  current_summary: summary(8),
  ...overrides,
});

describe("describeSummary", () => {
  it("describes rows and range", () => {
    expect(describeSummary(summary(699))).toBe("699 movimientos · 14 ene 2025 – 13 oct 2026");
    expect(describeSummary({ ...summary(1), date_from: null, date_to: null })).toBe("1 movimiento");
    expect(describeSummary(null)).toBe("Sin extracto cargado");
  });
});

describe("rowDifference", () => {
  it("compares with the current extract", () => {
    expect(rowDifference(report())).toBe(2);
    expect(rowDifference(report({ current_summary: null }))).toBeNull();
  });
});

describe("replaceButtonLabel", () => {
  it("depends on validity and warnings", () => {
    expect(replaceButtonLabel(report())).toBe("Sustituir extracto");
    expect(replaceButtonLabel(report({ warnings: ["x"] }))).toBe("Sustituir igualmente");
    expect(replaceButtonLabel(report({ is_valid: false, errors: ["x"] }))).toBe("No se puede sustituir");
  });
});
