"""Request and response models of the API (they also document it at /docs)."""

import datetime
from typing import Literal

from pydantic import BaseModel, Field


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


class FlowSummaryRow(BaseModel):
    """Money in, out and net of the filtered transactions, per group."""

    month: str | None = None
    category: str | None = None
    merchant: str | None = None
    flow_type: str | None = None
    inflow_eur: float
    outflow_eur: float
    net_eur: float
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


class SalaryStepModel(BaseModel):
    """Yearly gross salary and bonus in force from ``start_month``."""

    start_month: str = Field(pattern=r"^\d{4}-\d{2}$")
    gross_salary_eur: float = Field(ge=0)
    gross_bonus_eur: float = Field(0.0, ge=0)


class ScenarioParametersModel(BaseModel):
    """Inputs of one projection scenario (annual nominal rates as fractions)."""

    horizon_years: int = Field(10, ge=1, le=50)
    start_cash_eur: float = 0.0
    start_investments_eur: float = Field(0.0, ge=0)
    salary_schedule: list[SalaryStepModel] = Field(default_factory=list, max_length=20)
    salary_growth: float = Field(0.0, ge=-0.5, le=0.5)
    payments_per_year: Literal[12, 14] = 14
    bonus_month: int = Field(7, ge=1, le=12)
    retention_rate_override: float | None = Field(None, ge=0, le=0.6)
    monthly_other_income_eur: float = Field(0.0, ge=0)
    monthly_expenses_eur: float = Field(0.0, ge=0)
    inflation: float = Field(0.0, ge=-0.1, le=0.5)
    monthly_investment_eur: float = Field(0.0, ge=0)
    investment_growth: float = Field(0.0, ge=-0.5, le=0.5)
    cash_return: float = Field(0.0, ge=-0.1, le=0.5)
    investment_return: float = Field(0.0, ge=-0.5, le=0.5)
    investment_volatility: float = Field(0.0, ge=0, le=1)


class ScenarioRequest(BaseModel):
    """A named scenario to simulate."""

    name: str
    parameters: ScenarioParametersModel


class SimulationRequest(BaseModel):
    """Scenarios to compare, optionally with a Monte Carlo spread."""

    scenarios: list[ScenarioRequest] = Field(min_length=1, max_length=8)
    simulations: int = Field(500, ge=0, le=5000)
    start_month: str | None = Field(None, pattern=r"^\d{4}-\d{2}$")


class ProjectionPoint(BaseModel):
    """One projected month."""

    month: str
    cash_eur: float
    investments_eur: float
    total_eur: float
    total_real_eur: float
    invested_principal_eur: float
    salary_eur: float
    tax_refund_eur: float
    other_income_eur: float
    expenses_eur: float
    contribution_eur: float


class PercentilePoint(BaseModel):
    """Monte Carlo spread of the total net worth in one month."""

    month: str
    p10_eur: float
    p50_eur: float
    p90_eur: float


class ProjectionSummary(BaseModel):
    """Headline numbers of a scenario at its horizon."""

    final_cash_eur: float
    final_investments_eur: float
    final_total_eur: float
    final_total_real_eur: float
    start_total_eur: float
    total_contributions_eur: float
    investment_gains_eur: float
    first_negative_cash_month: str | None


class PayrollYear(BaseModel):
    """Payroll of one calendar year and its IRPF settlement."""

    year: int
    gross_eur: float
    social_security_eur: float
    retention_eur: float
    net_eur: float
    tax_liability_eur: float
    refund_eur: float
    retention_rate: float
    regular_month_net_eur: float
    extra_pay_net_eur: float
    bonus_net_eur: float


class ScenarioResult(BaseModel):
    """Projection of one scenario."""

    name: str
    summary: ProjectionSummary
    payroll_years: list[PayrollYear]
    points: list[ProjectionPoint]
    percentiles: list[PercentilePoint]
