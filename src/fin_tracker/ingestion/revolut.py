"""Revolut extract parser: one csv holding a transaction table per wallet."""

import csv
import io
from pathlib import Path

import pandas as pd

from fin_tracker.config import FILE_NAME_REVOLUT, PATH_RAW_DATA
from fin_tracker.schema import conform_to_schema

# Line that precedes every wallet's transaction table
WALLET_TABLE_MARKER = "Extracto de transacción"
WALLET_TABLE_HEADER_START = "Fecha"
WALLET_TABLE_END = "Total"

REVOLUT_COLUMN_NAMES = {
    "Fecha": "date",
    "Descripción": "description",
    "Categoría": "category",
    "Entradas/salidas de dinero": "amount",
    "Saldo": "balance",
    "Impuestos retenidos": "taxes_withheld",
    "Otros impuestos": "other_taxes",
    "Comisiones": "fees",
}
MONEY_COLUMNS = ["amount", "balance", "taxes_withheld", "other_taxes", "fees"]

SPANISH_MONTHS = {
    "ene": "01", "feb": "02", "mar": "03", "abr": "04", "may": "05", "jun": "06",
    "jul": "07", "ago": "08", "sep": "09", "sept": "09", "oct": "10", "nov": "11",
    "dic": "12",
}  # fmt: skip


def get_first_cell(line: str) -> str:
    """Return the stripped first csv cell of a line, or an empty string."""
    return next(csv.reader([line]), [""])[0].strip() if line else ""


def parse_money(series_money: pd.Series) -> pd.Series:
    """Parse Spanish formatted money strings such as ``"-1.144,34€"`` to floats.

    Args:
        series_money: Strings with thousands dots, decimal commas and currency symbols.

    Returns:
        Numeric series, NaN where parsing fails.
    """
    series_clean = (
        series_money.astype(str)
        .str.replace("\u2212", "-", regex=False)  # Unicode minus sign
        .str.replace(r"[^\d,.\-]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(series_clean, errors="coerce")


def parse_spanish_date(series_date: pd.Series) -> pd.Series:
    """Parse dates like ``"8 jul 2025"`` with Spanish month abbreviations.

    Args:
        series_date: Date strings as ``day month_abbreviation year``.

    Returns:
        Datetime series.
    """
    df_date_parts = series_date.str.split(expand=True)
    series_iso = (
        df_date_parts[2]
        + "-"
        + df_date_parts[1].str.lower().map(SPANISH_MONTHS)
        + "-"
        + df_date_parts[0].str.zfill(2)
    )
    return pd.to_datetime(series_iso, format="%Y-%m-%d")


def rename_revolut_column(column_name: str) -> str:
    """Translate a Revolut column name, mapping pandas' ``.1`` duplicates to ``_eur``.

    Foreign currency wallets repeat each money column with its EUR equivalent.
    """
    base_column_name = column_name.removesuffix(".1")
    suffix = "_eur" if column_name.endswith(".1") else ""
    return REVOLUT_COLUMN_NAMES.get(base_column_name, base_column_name) + suffix


def read_wallet_table(list_lines: list[str], index_marker: int) -> pd.DataFrame:
    """Parse the transaction table of a single wallet.

    Args:
        list_lines: All lines of the Revolut csv.
        index_marker: Line index of the wallet's ``WALLET_TABLE_MARKER``.

    Returns:
        Wallet movements with translated column names and numeric money columns,
        or an empty dataframe if the wallet has no movements.
    """
    # The wallet name is the closest non-empty line above the marker
    wallet_name = next(
        get_first_cell(list_lines[index_line])
        for index_line in range(index_marker - 1, -1, -1)
        if get_first_cell(list_lines[index_line])
    )
    index_header = index_marker + 1
    # Wallets without movements have a separator instead of a header row
    if get_first_cell(list_lines[index_header]) != WALLET_TABLE_HEADER_START:
        return pd.DataFrame()

    # The table ends at its "Total" row, or at the first blank / separator line
    index_table_end = next(
        (
            index_line
            for index_line in range(index_header + 1, len(list_lines))
            if get_first_cell(list_lines[index_line]) in (WALLET_TABLE_END, "")
            or get_first_cell(list_lines[index_line]).startswith("---")
        ),
        len(list_lines),
    )

    df_wallet = pd.read_csv(
        io.StringIO("\n".join(list_lines[index_header:index_table_end]))
    )
    df_wallet = df_wallet.loc[:, ~df_wallet.columns.str.startswith("Unnamed")]
    df_wallet = df_wallet.rename(columns=rename_revolut_column)

    for money_column in MONEY_COLUMNS:
        # EUR wallets have no separate EUR columns, they are the same values
        if f"{money_column}_eur" not in df_wallet.columns:
            df_wallet[f"{money_column}_eur"] = df_wallet[money_column]
        df_wallet[money_column] = parse_money(df_wallet[money_column])
        df_wallet[f"{money_column}_eur"] = parse_money(df_wallet[f"{money_column}_eur"])

    df_wallet["wallet"] = wallet_name
    return df_wallet


def read_revolut_raw(
    path_file: Path = PATH_RAW_DATA / FILE_NAME_REVOLUT,
) -> pd.DataFrame:
    """Read every wallet table of the Revolut csv into a single dataframe.

    Args:
        path_file: Path to the Revolut csv extract.

    Returns:
        Raw movements of all wallets, with ``wallet`` and ``currency`` columns.

    Raises:
        ValueError: If the file has no wallet transaction table.
    """
    list_lines = path_file.read_text(encoding="utf-8").splitlines()
    list_marker_indices = [
        index_line
        for index_line, line in enumerate(list_lines)
        if get_first_cell(line) == WALLET_TABLE_MARKER
    ]
    if not list_marker_indices:
        raise ValueError(f"no wallet tables found (no '{WALLET_TABLE_MARKER}' line)")
    list_df_wallets = [
        read_wallet_table(list_lines, index_marker)
        for index_marker in list_marker_indices
    ]
    df_revolut_raw = pd.concat(
        [df_wallet for df_wallet in list_df_wallets if not df_wallet.empty],
        ignore_index=True,
    )
    # Wallet names end with their currency, e.g. "Cuenta personal (HUF)"
    df_revolut_raw["currency"] = df_revolut_raw["wallet"].str.extract(r"\((\w{3})\)")[0]
    return df_revolut_raw


def normalize_revolut(df_revolut_raw: pd.DataFrame) -> pd.DataFrame:
    """Map raw Revolut movements to the unified schema.

    ``amount`` already has fees deducted (balances reconcile on ``amount`` alone),
    so ``fee`` and ``tax`` are informational and must not be added again.

    Args:
        df_revolut_raw: Output of :func:`read_revolut_raw`.

    Returns:
        Revolut transactions in the unified schema.
    """
    df_revolut = pd.DataFrame(
        {
            "account": "revolut",
            "sub_account": df_revolut_raw["wallet"],
            "date": parse_spanish_date(df_revolut_raw["date"]),
            "bank_category": df_revolut_raw["category"],
            "description": df_revolut_raw["description"],
            "amount": df_revolut_raw["amount"],
            "currency": df_revolut_raw["currency"],
            "amount_eur": df_revolut_raw["amount_eur"],
            # Revolut reports fees and taxes as positive costs, flip to the cash flow sign
            "fee": -df_revolut_raw["fees"],
            "fee_eur": -df_revolut_raw["fees_eur"],
            "tax": -(df_revolut_raw["taxes_withheld"] + df_revolut_raw["other_taxes"]),
            "tax_eur": -(
                df_revolut_raw["taxes_withheld_eur"] + df_revolut_raw["other_taxes_eur"]
            ),
            "balance": df_revolut_raw["balance"],
            "balance_eur": df_revolut_raw["balance_eur"],
        }
    )
    return conform_to_schema(df_revolut)


def load_revolut(path_file: Path = PATH_RAW_DATA / FILE_NAME_REVOLUT) -> pd.DataFrame:
    """Read and normalize the Revolut extract.

    Args:
        path_file: Path to the Revolut csv extract.

    Returns:
        Revolut transactions in the unified schema.
    """
    return normalize_revolut(read_revolut_raw(path_file))
