// Human labels for the identifiers the API returns

import type { FlowType } from "../api/types";

export const ACCOUNT_LABELS: Record<string, string> = {
  bbva: "BBVA",
  revolut: "Revolut",
  trade_republic: "Trade Republic",
};

export const FLOW_TYPE_LABELS: Record<FlowType, string> = {
  expense: "Gasto",
  income: "Ingreso",
  internal_transfer: "Traspaso interno",
  investment: "Inversión",
  investment_income: "Rendimiento",
  excluded: "Excluido",
};

export const ASSET_BUCKET_LABELS: Record<string, string> = {
  equity: "Renta variable",
  fixed_income: "Renta fija",
  commodities: "Materias primas",
};

/** Account label, falling back to the raw identifier. */
export function labelAccount(account: string): string {
  return ACCOUNT_LABELS[account] ?? account;
}

/** Wallet label: "Revolut · Cuenta personal (EUR)" or just "BBVA". */
export function labelWallet(account: string, subAccount: string | null): string {
  if (!subAccount) return labelAccount(account);
  const prettySubAccount = subAccount === "cash" ? "Efectivo" : subAccount;
  return `${labelAccount(account)} · ${prettySubAccount}`;
}

export function labelAssetBucket(bucket: string): string {
  return ASSET_BUCKET_LABELS[bucket] ?? bucket;
}
