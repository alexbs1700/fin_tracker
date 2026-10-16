// Thin typed wrappers around the local API, consumed through TanStack Query hooks

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type {
  BankKey,
  CategoryCatalog,
  ExtractReplaceResult,
  ExtractReport,
  ExtractStatus,
  FlowSummaryRow,
  FlowType,
  LiquidityPoint,
  MonthlyCashFlow,
  MonthlyNetWorthStats,
  NetWorthSummary,
  PortfolioPoint,
  PortfolioSummary,
  ScenarioParameters,
  ScenarioResult,
  Transaction,
  TransactionPage,
} from "./types";

export type QueryParams = Record<string, string | number | string[] | undefined | null>;

/** Build a query string, repeating keys for arrays and skipping empty values. */
export function buildQueryString(params: QueryParams): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) searchParams.append(key, String(item));
  }
  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} on ${path}`);
  }
  return response.json() as Promise<T>;
}

export const useNetWorth = () =>
  useQuery({
    queryKey: ["net-worth"],
    queryFn: () => requestJson<NetWorthSummary>("/api/net-worth"),
  });

export const useNetWorthHistory = (params: QueryParams) =>
  useQuery({
    queryKey: ["net-worth-history", params],
    queryFn: () =>
      requestJson<LiquidityPoint[]>(`/api/net-worth/history${buildQueryString(params)}`),
  });

export const useNetWorthMonthlyStats = (params: QueryParams) =>
  useQuery({
    queryKey: ["net-worth-monthly-stats", params],
    queryFn: () =>
      requestJson<MonthlyNetWorthStats[]>(
        `/api/net-worth/monthly-stats${buildQueryString(params)}`,
      ),
  });

export const useTransactions = (params: QueryParams) =>
  useQuery({
    queryKey: ["transactions", params],
    queryFn: () =>
      requestJson<TransactionPage>(`/api/transactions${buildQueryString(params)}`),
    placeholderData: (previousData) => previousData,
  });

export const useTransactionLegs = (transactionKey: string | null) =>
  useQuery({
    queryKey: ["transaction", transactionKey],
    queryFn: () => requestJson<Transaction[]>(`/api/transactions/${transactionKey}`),
    enabled: transactionKey !== null,
  });

export const useCategories = () =>
  useQuery({
    queryKey: ["categories"],
    queryFn: () => requestJson<CategoryCatalog>("/api/categories"),
  });

export const useTransactionsSummary = (params: QueryParams) =>
  useQuery({
    queryKey: ["transactions-summary", params],
    queryFn: () =>
      requestJson<FlowSummaryRow[]>(`/api/transactions/summary${buildQueryString(params)}`),
    placeholderData: (previousData) => previousData,
  });

export const useMonthlyCashFlow = (params: QueryParams) =>
  useQuery({
    queryKey: ["cash-flow", params],
    queryFn: () =>
      requestJson<MonthlyCashFlow[]>(`/api/cash-flow/monthly${buildQueryString(params)}`),
  });

export const usePortfolio = () =>
  useQuery({
    queryKey: ["portfolio"],
    queryFn: () => requestJson<PortfolioSummary>("/api/portfolio"),
  });

export const usePortfolioHistory = (params: QueryParams) =>
  useQuery({
    queryKey: ["portfolio-history", params],
    queryFn: () =>
      requestJson<PortfolioPoint[]>(`/api/portfolio/history${buildQueryString(params)}`),
  });

/** Save a manual category; every spending view depending on it is refreshed. */
export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      transactionKey,
      category,
      flowType,
    }: {
      transactionKey: string;
      category: string;
      flowType?: FlowType;
    }) =>
      requestJson<Transaction>(`/api/transactions/${transactionKey}/category`, {
        method: "PATCH",
        body: JSON.stringify({ category, flow_type: flowType ?? null }),
      }),
    onSuccess: () => {
      for (const queryKey of [
        "transactions",
        "transactions-summary",
        "cash-flow",
        "categories",
        "transaction",
      ]) {
        queryClient.invalidateQueries({ queryKey: [queryKey] });
      }
    },
  });
}

export const useExtracts = () =>
  useQuery({
    queryKey: ["extracts"],
    queryFn: () => requestJson<ExtractStatus[]>("/api/extracts"),
  });

/** POST a file as multipart; the browser sets the boundary header itself. */
async function uploadExtract<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(path, { method: "POST", body: formData });
  const body = await response.json();
  if (!response.ok) {
    // A refused replacement carries the validation report as its detail
    if (response.status === 422 && typeof body.detail === "object") return body.detail as T;
    throw new Error(typeof body.detail === "string" ? body.detail : `${response.status} on ${path}`);
  }
  return body as T;
}

export const useValidateExtract = () =>
  useMutation({
    mutationFn: ({ bank, file }: { bank: BankKey; file: File }) =>
      uploadExtract<ExtractReport>(`/api/extracts/${bank}/validate`, file),
  });

/** Replace a bank's extract; every view is refreshed with the new data. */
export function useReplaceExtract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ bank, file }: { bank: BankKey; file: File }) => {
      const body = await uploadExtract<ExtractReplaceResult | ExtractReport>(`/api/extracts/${bank}`, file);
      // A refused replacement answers with the bare report
      return "report" in body ? body : { report: body, backup_file: null };
    },
    onSuccess: (result) => {
      if (result.report.is_valid) queryClient.invalidateQueries();
    },
  });
}

export const useProjectionBaseline = () =>
  useQuery({
    queryKey: ["projection-baseline"],
    queryFn: () => requestJson<ScenarioParameters>("/api/projections/baseline"),
  });

/** Simulate every scenario; it is fast, so it simply reruns on every edit. */
export const useSimulation = (
  scenarios: { name: string; parameters: ScenarioParameters }[],
  simulations = 500,
) =>
  useQuery({
    queryKey: ["simulation", scenarios, simulations],
    queryFn: () =>
      requestJson<ScenarioResult[]>("/api/projections/simulate", {
        method: "POST",
        body: JSON.stringify({ scenarios, simulations }),
      }),
    enabled: scenarios.length > 0,
    placeholderData: (previousData) => previousData,
  });
