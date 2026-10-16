import { describe, expect, it } from "vitest";

import type { FlowSummaryRow } from "../api/types";
import { activeFlowSeries, describeTotal, shareOfAbsoluteTotal, toggleFlowType } from "./movements";

const row = (inflow: number, outflow: number, extra: Partial<FlowSummaryRow> = {}): FlowSummaryRow => ({
  month: null,
  category: null,
  merchant: null,
  flow_type: null,
  inflow_eur: inflow,
  outflow_eur: outflow,
  net_eur: inflow - outflow,
  transactions: 1,
  ...extra,
});

describe("toggleFlowType", () => {
  it("adds and removes", () => {
    expect(toggleFlowType(["expense"], "income")).toEqual(["expense", "income"]);
    expect(toggleFlowType(["expense", "income"], "expense")).toEqual(["income"]);
  });
});

describe("describeTotal", () => {
  it("shows spending as a positive amount", () => {
    expect(describeTotal(["expense"], row(10, 110))).toEqual({ label: "Gasto en el periodo", value: 100, isSigned: false });
  });

  it("shows income-like selections as income", () => {
    expect(describeTotal(["income", "investment_income"], row(50, 0)).label).toBe("Ingresos en el periodo");
  });

  it("shows the signed net for mixes and for everything", () => {
    expect(describeTotal(["income", "expense"], row(100, 130))).toEqual({ label: "Neto del periodo", value: -30, isSigned: true });
    expect(describeTotal([], undefined)).toEqual({ label: "Neto del periodo", value: 0, isSigned: true });
  });
});

describe("activeFlowSeries", () => {
  it("keeps only the series with money", () => {
    expect(activeFlowSeries(row(0, 10))).toEqual(["outflow_eur"]);
    expect(activeFlowSeries(row(5, 10))).toEqual(["inflow_eur", "outflow_eur"]);
    expect(activeFlowSeries(row(0, 0))).toEqual(["outflow_eur"]);
  });
});

describe("shareOfAbsoluteTotal", () => {
  it("uses absolute nets", () => {
    const rows = [row(0, 75), row(25, 0)];
    expect(shareOfAbsoluteTotal(rows[0], rows)).toBe(0.75);
    expect(shareOfAbsoluteTotal(row(0, 0), [])).toBe(0);
  });
});

describe("describeTotal without data", () => {
  it("never shows a negative zero", () => {
    expect(Object.is(describeTotal(["expense"], undefined).value, -0)).toBe(false);
  });
});
