// Presentation helpers for bank extracts

import type { ExtractReport, ExtractSummary } from "../api/types";
import { formatDate } from "./format";

/** "699 movimientos · 14 ene 2025 – 13 oct 2026" */
export function describeSummary(summary: ExtractSummary | null): string {
  if (!summary) return "Sin extracto cargado";
  const movements = `${summary.rows} ${summary.rows === 1 ? "movimiento" : "movimientos"}`;
  if (!summary.date_from || !summary.date_to) return movements;
  return `${movements} · ${formatDate(summary.date_from)} – ${formatDate(summary.date_to)}`;
}

/** Rows the replacement adds (positive) or removes (negative) against the current extract. */
export function rowDifference(report: ExtractReport): number | null {
  if (!report.summary || !report.current_summary) return null;
  return report.summary.rows - report.current_summary.rows;
}

/** Label of the replace button: plain when clean, explicit when there are warnings. */
export function replaceButtonLabel(report: ExtractReport): string {
  if (!report.is_valid) return "No se puede sustituir";
  return report.warnings.length ? "Sustituir igualmente" : "Sustituir extracto";
}
