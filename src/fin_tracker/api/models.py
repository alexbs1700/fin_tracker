"""Request and response models of the API (they also document it at /docs)."""

import datetime

from pydantic import BaseModel


class AccountValue(BaseModel):
    """Value of one account split by asset type."""

    account: str
    asset_type: str
    value_eur: float


class CashWallet(BaseModel):
    """Current balance of one account or wallet."""

    account: str
    sub_account: str | None
    currency: str
    balance: float
    balance_eur: float
    ownership_share: float
    my_balance_eur: float


class NetWorthSummary(BaseModel):
    """Current net worth split into liquid cash and investments."""

    total_eur: float
    cash_eur: float
    investments_eur: float
    by_account: list[AccountValue]
    cash_wallets: list[CashWallet]


class LiquidityPoint(BaseModel):
    """Net worth on one day, split into cash and investments."""

    date: datetime.date
    cash_eur: float
    investments_eur: float
    total_eur: float


class MonthlyNetWorthStats(BaseModel):
    """Distribution of the daily net worth within one month."""

    month: str
    min_eur: float
    max_eur: float
    mean_eur: float
    median_eur: float
    min_date: datetime.date
    max_date: datetime.date
    days: int
    is_partial: bool


class AccountPoint(BaseModel):
    """Value of one account and asset type on one day."""

    date: datetime.date
    account: str
    asset_type: str
    value_eur: float | None


class Transaction(BaseModel):
    """A categorized transaction."""

    transaction_key: str
    date: datetime.date
    account: str
    sub_account: str | None
    description: str | None
    details: str | None
    amount: float
    currency: str
    amount_eur: float | None
    flow_type: str
    category: str
    bank_category: str | None
    transfer_id: str | None
    transfer_counterparty_key: str | None
    is_category_override: bool


class TransactionPage(BaseModel):
    """A page of filtered transactions, newest first."""

    total: int
    items: list[Transaction]


class CategoryUpdate(BaseModel):
    """Manual correction of a transaction's category."""

    category: str
    flow_type: str | None = None


class CategoryCatalog(BaseModel):
    """Every category and flow type the UI can offer."""

    categories: list[str]
    flow_types: list[str]


class SpendingRow(BaseModel):
    """Spending aggregated by month, category or merchant."""

    month: str | None = None
    category: str | None = None
    merchant: str | None = None
    spent_eur: float
    transactions: int


class MonthlyCashFlow(BaseModel):
    """Income, spending, savings and investing of one month."""

    month: str
    income_eur: float
    expenses_eur: float
    savings_eur: float
    savings_rate: float | None
    invested_eur: float


class Position(BaseModel):
    """An open investment valued at the latest price."""

    asset_isin: str
    asset_name: str | None
    asset_class: str | None
    asset_bucket: str
    ticker: str | None
    shares: float
    cost_basis_eur: float
    average_cost_eur: float
    last_price_eur: float | None
    market_value_eur: float | None
    unrealized_gain_eur: float | None
    unrealized_return: float | None
    weight: float | None


class RealizedGain(BaseModel):
    """Gain of one sell, with FIFO cost."""

    date: datetime.date
    asset_isin: str
    asset_name: str | None
    shares_sold: float
    proceeds_eur: float
    cost_basis_eur: float
    realized_gain_eur: float


class PortfolioSummary(BaseModel):
    """Open positions, realized gains and totals."""

    market_value_eur: float
    cost_basis_eur: float
    unrealized_gain_eur: float
    unrealized_return: float | None
    realized_gain_eur: float
    allocation: dict[str, float]
    positions: list[Position]
    realized_gains: list[RealizedGain]


class PortfolioPoint(BaseModel):
    """Portfolio value and cost basis on one day, optionally per group."""

    date: datetime.date
    group: str | None = None
    cost_basis_eur: float
    market_value_eur: float | None


class ExtractSummaryModel(BaseModel):
    """Rows, date range and wallets of an extract."""

    rows: int
    date_from: datetime.date | None
    date_to: datetime.date | None
    sub_accounts: list[str]


class ExtractStatus(BaseModel):
    """The extract currently loaded for one bank."""

    bank: str
    label: str
    file_name: str
    extension: str
    exists: bool
    modified_at: datetime.datetime | None
    summary: ExtractSummaryModel | None


class ExtractReportModel(BaseModel):
    """Validation result of an uploaded extract."""

    bank: str
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    summary: ExtractSummaryModel | None
    current_summary: ExtractSummaryModel | None


class ExtractReplaceResult(BaseModel):
    """Outcome of replacing an extract."""

    report: ExtractReportModel
    backup_file: str | None
