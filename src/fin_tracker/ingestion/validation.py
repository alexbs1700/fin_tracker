"""Checks that an uploaded extract can safely replace the current one.

Errors block the replacement (the file would break the app or be read
wrongly); warnings are shown to the user, who decides.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from fin_tracker.ingestion.banks import Bank
from fin_tracker.schema import compute_net_cash_eur

# Trade Republic transaction types the categorization rules know about
KNOWN_TRADE_REPUBLIC_TYPES = {
    "BUY", "SELL", "DIVIDEND", "INTEREST_PAYMENT", "CUSTOMER_INPAYMENT",
    "CARD_TRANSACTION", "TRANSFER_INBOUND", "TRANSFER_OUTBOUND",
}  # fmt: skip
BALANCE_TOLERANCE_EUR = 0.01


@dataclass
class ExtractSummary:
    """What an extract contains."""

    rows: int
    date_from: pd.Timestamp | None
    date_to: pd.Timestamp | None
    sub_accounts: list[str] = field(default_factory=list)


@dataclass
class ExtractReport:
    """Result of validating an extract against the bank's parsing rules."""

    bank: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: ExtractSummary | None = None
    current_summary: ExtractSummary | None = None

    @property
    def is_valid(self) -> bool:
        """True when nothing blocks replacing the current extract."""
        return not self.errors


def summarize_transactions(df_transactions: pd.DataFrame) -> ExtractSummary:
    """Row count, date range and wallets of normalized transactions."""
    return ExtractSummary(
        rows=len(df_transactions),
        date_from=df_transactions["date"].min() if len(df_transactions) else None,
        date_to=df_transactions["date"].max() if len(df_transactions) else None,
        sub_accounts=sorted(df_transactions["sub_account"].dropna().unique().tolist()),
    )


def count_balance_breaks(df_transactions: pd.DataFrame) -> int:
    """Rows whose balance is not the previous balance plus their amount.

    In a correctly parsed, correctly ordered extract every row satisfies this,
    so any break means missing rows, a wrong order or misread amounts.

    Args:
        df_transactions: Normalized transactions of a running-balance bank.

    Returns:
        Number of rows breaking the running balance, per wallet.
    """
    breaks = 0
    for _, df_wallet in df_transactions.groupby(
        "sub_account", dropna=False, sort=False
    ):
        series_expected = df_wallet["balance"].shift(1) + df_wallet["amount"]
        series_gap = (df_wallet["balance"] - series_expected).abs().iloc[1:]
        breaks += int((series_gap > BALANCE_TOLERANCE_EUR).sum())
    return breaks


def check_normalized(
    bank: Bank, df_transactions: pd.DataFrame
) -> tuple[list[str], list[str]]:
    """Content checks on normalized transactions.

    Args:
        bank: Bank the extract belongs to.
        df_transactions: Output of ``bank.normalize``.

    Returns:
        A tuple ``(errors, warnings)``.
    """
    list_errors: list[str] = []
    list_warnings: list[str] = []

    if df_transactions.empty:
        return ["El extracto no contiene movimientos."], list_warnings
    if df_transactions["date"].isna().any():
        list_errors.append(
            f"{df_transactions['date'].isna().sum()} filas con fecha ilegible."
        )
    if df_transactions["amount"].isna().any():
        list_errors.append(
            f"{df_transactions['amount'].isna().sum()} filas con importe ilegible."
        )

    if bank.has_running_balance:
        balance_breaks = count_balance_breaks(df_transactions)
        if balance_breaks:
            list_errors.append(
                f"{balance_breaks} filas cuyo saldo no cuadra con el anterior más el importe: "
                "faltan filas o el formato ha cambiado."
            )

    if bank.key == "trade_republic":
        if df_transactions["transaction_id"].isna().any():
            list_errors.append("Hay movimientos sin transaction_id.")
        elif df_transactions["transaction_id"].duplicated().any():
            list_errors.append("Hay transaction_id duplicados.")
        is_trade = df_transactions["transaction_type"].isin(["BUY", "SELL"])
        if df_transactions.loc[is_trade, ["asset_isin", "shares"]].isna().any().any():
            list_errors.append(
                "Hay compras o ventas sin ISIN o sin número de participaciones."
            )
        set_unknown_types = (
            set(df_transactions["transaction_type"].dropna())
            - KNOWN_TRADE_REPUBLIC_TYPES
        )
        if set_unknown_types:
            list_warnings.append(
                f"Tipos de movimiento nuevos: {', '.join(sorted(set_unknown_types))}. "
                "Se clasificarán como ingreso o gasto genérico hasta añadir una regla."
            )
        if compute_net_cash_eur(df_transactions).sum() < -BALANCE_TOLERANCE_EUR:
            list_warnings.append(
                "El efectivo reconstruido sale negativo: ¿falta historial antiguo?"
            )

    return list_errors, list_warnings


def compare_with_current(
    summary: ExtractSummary, current_summary: ExtractSummary
) -> list[str]:
    """Warn when the new extract would drop history the current one has.

    Args:
        summary: The uploaded extract.
        current_summary: The extract it would replace.

    Returns:
        Warning messages.
    """
    list_warnings = []
    if (
        current_summary.date_from is not None
        and summary.date_from is not None
        and summary.date_from > current_summary.date_from
    ):
        list_warnings.append(
            f"El nuevo extracto empieza el {summary.date_from:%d/%m/%Y} y el actual el "
            f"{current_summary.date_from:%d/%m/%Y}: se perderán los movimientos anteriores."
        )
    if (
        current_summary.date_to is not None
        and summary.date_to is not None
        and summary.date_to < current_summary.date_to
    ):
        list_warnings.append(
            f"El nuevo extracto acaba el {summary.date_to:%d/%m/%Y}, antes que el actual "
            f"({current_summary.date_to:%d/%m/%Y})."
        )
    set_missing_wallets = set(current_summary.sub_accounts) - set(summary.sub_accounts)
    if set_missing_wallets:
        list_warnings.append(
            f"Carteras que desaparecen: {', '.join(sorted(set_missing_wallets))}."
        )
    return list_warnings


def load_summary(bank: Bank, path_file: Path) -> ExtractSummary | None:
    """Summary of an existing extract, or None if it is missing or unreadable."""
    if not path_file.exists():
        return None
    try:
        return summarize_transactions(bank.normalize(bank.read_raw(path_file)))
    except Exception:  # A broken current file must not block replacing it
        return None


def validate_extract(
    bank: Bank, path_upload: Path, path_current: Path
) -> ExtractReport:
    """Validate an uploaded extract and compare it with the current one.

    Args:
        bank: Bank the upload claims to be from.
        path_upload: Uploaded file, saved with the bank's extension.
        path_current: Extract it would replace (may not exist).

    Returns:
        The validation report.
    """
    report = ExtractReport(
        bank=bank.key, current_summary=load_summary(bank, path_current)
    )

    try:
        df_raw = bank.read_raw(path_upload)
    except Exception as error:  # Any parser failure is a user-facing error
        report.errors.append(f"No se puede leer como extracto de {bank.label}: {error}")
        return report

    list_missing_columns = [
        column for column in bank.required_columns if column not in df_raw.columns
    ]
    if list_missing_columns:
        report.errors.append(
            f"Faltan columnas esperadas en un extracto de {bank.label}: "
            f"{', '.join(list_missing_columns)}."
        )
        return report

    try:
        df_transactions = bank.normalize(df_raw)
    except Exception as error:
        report.errors.append(f"Las filas no tienen el formato esperado: {error}")
        return report

    list_errors, list_warnings = check_normalized(bank, df_transactions)
    report.errors.extend(list_errors)
    report.warnings.extend(list_warnings)
    if df_transactions.empty:
        return report

    report.summary = summarize_transactions(df_transactions)
    if report.current_summary is not None:
        report.warnings.extend(
            compare_with_current(report.summary, report.current_summary)
        )
    return report
