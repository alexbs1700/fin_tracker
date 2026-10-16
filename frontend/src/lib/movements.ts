// How the Movimientos page summarizes whatever selection of flow types is active

import type { FlowSummaryRow, FlowType } from "../api/types";

export const INFLOW_FLOW_TYPES: FlowType[] = ["income", "investment_income"];

/** Add or remove a flow type from the selection (empty selection = every type). */
export function toggleFlowType(selected: FlowType[], flowType: FlowType): FlowType[] {
  return selected.includes(flowType)
    ? selected.filter((selectedType) => selectedType !== flowType)
    : [...selected, flowType];
}

/**
 * Headline of the selection: spending reads as a positive "Gasto", income as
 * "Ingresos"; any mix (or everything) shows the signed net.
 */
export function describeTotal(
  selected: FlowType[],
  total: FlowSummaryRow | undefined,
): { label: string; value: number; isSigned: boolean } {
  const net = total?.net_eur ?? 0;
  if (selected.length > 0 && selected.every((flowType) => flowType === "expense")) {
    // "|| 0" avoids showing −0,00 € before data arrives
    return { label: "Gasto en el periodo", value: -net || 0, isSigned: false };
  }
  if (selected.length > 0 && selected.every((flowType) => INFLOW_FLOW_TYPES.includes(flowType))) {
    return { label: "Ingresos en el periodo", value: net, isSigned: false };
  }
  return { label: "Neto del periodo", value: net, isSigned: true };
}

/** Which of the in / out series carry money in this selection. */
export function activeFlowSeries(total: FlowSummaryRow | undefined): ("inflow_eur" | "outflow_eur")[] {
  if (!total) return ["outflow_eur"];
  const series: ("inflow_eur" | "outflow_eur")[] = [];
  if (total.inflow_eur > 0) series.push("inflow_eur");
  if (total.outflow_eur > 0) series.push("outflow_eur");
  return series.length ? series : ["outflow_eur"];
}

/** Share of each row in the sum of absolute nets, so mixed signs still add to 100 %. */
export function shareOfAbsoluteTotal(row: FlowSummaryRow, rows: FlowSummaryRow[]): number {
  const absoluteTotal = rows.reduce((sum, item) => sum + Math.abs(item.net_eur), 0);
  return absoluteTotal ? Math.abs(row.net_eur) / absoluteTotal : 0;
}
