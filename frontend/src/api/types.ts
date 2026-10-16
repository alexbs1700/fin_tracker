// Response shapes of the FastAPI backend (see src/fin_tracker/api/models.py)

export type FlowType =
  | "internal_transfer"
  | "investment"
  | "investment_income"
  | "income"
  | "expense"
  | "excluded";

export interface AccountValue {
  account: string;
  asset_type: "cash" | "investments";
  value_eur: number;
}

export interface CashWallet {
  account: string;
  sub_account: string | null;
  currency: string;
  balance: number;
  balance_eur: number;
  ownership_share: number;
  my_balance_eur: number;
}

export interface NetWorthSummary {
  total_eur: number;
  cash_eur: number;
  investments_eur: number;
  by_account: AccountValue[];
  cash_wallets: CashWallet[];
}

export interface LiquidityPoint {
  date: string;
  cash_eur: number;
  investments_eur: number;
  total_eur: number;
}

export interface Transaction {
  transaction_key: string;
  date: string;
  account: string;
  sub_account: string | null;
  description: string | null;
  details: string | null;
  amount: number;
  currency: string;
  amount_eur: number | null;
  flow_type: FlowType;
  category: string;
  bank_category: string | null;
  transfer_id: string | null;
  transfer_counterparty_key: string | null;
  is_category_override: boolean;
}

export interface TransactionPage {
  total: number;
  items: Transaction[];
}

export interface CategoryCatalog {
  categories: string[];
  flow_types: FlowType[];
}

export interface FlowSummaryRow {
  month: string | null;
  category: string | null;
  merchant: string | null;
  flow_type: FlowType | null;
  inflow_eur: number;
  outflow_eur: number;
  net_eur: number;
  transactions: number;
}

export interface MonthlyCashFlow {
  month: string;
  income_eur: number;
  expenses_eur: number;
  savings_eur: number;
  savings_rate: number | null;
  invested_eur: number;
}

export interface Position {
  asset_isin: string;
  asset_name: string | null;
  asset_class: string | null;
  asset_bucket: string;
  ticker: string | null;
  shares: number;
  cost_basis_eur: number;
  average_cost_eur: number;
  last_price_eur: number | null;
  market_value_eur: number | null;
  unrealized_gain_eur: number | null;
  unrealized_return: number | null;
  weight: number | null;
}

export interface RealizedGain {
  date: string;
  asset_isin: string;
  asset_name: string | null;
  shares_sold: number;
  proceeds_eur: number;
  cost_basis_eur: number;
  realized_gain_eur: number;
}

export interface PortfolioSummary {
  market_value_eur: number;
  cost_basis_eur: number;
  unrealized_gain_eur: number;
  unrealized_return: number | null;
  realized_gain_eur: number;
  allocation: Record<string, number>;
  positions: Position[];
  realized_gains: RealizedGain[];
}

export interface PortfolioPoint {
  date: string;
  group: string | null;
  cost_basis_eur: number;
  market_value_eur: number | null;
}

export interface MonthlyNetWorthStats {
  month: string;
  min_eur: number;
  max_eur: number;
  mean_eur: number;
  median_eur: number;
  min_date: string;
  max_date: string;
  days: number;
  is_partial: boolean;
}

export type BankKey = "bbva" | "revolut" | "trade_republic";

export interface ExtractSummary {
  rows: number;
  date_from: string | null;
  date_to: string | null;
  sub_accounts: string[];
}

export interface ExtractStatus {
  bank: BankKey;
  label: string;
  file_name: string;
  extension: string;
  exists: boolean;
  modified_at: string | null;
  summary: ExtractSummary | null;
}

export interface ExtractReport {
  bank: BankKey;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  summary: ExtractSummary | null;
  current_summary: ExtractSummary | null;
}

export interface ExtractReplaceResult {
  report: ExtractReport;
  backup_file: string | null;
}
