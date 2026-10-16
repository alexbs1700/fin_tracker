"""BBVA extract parser: single EUR account exported as xlsx."""

from pathlib import Path

import pandas as pd

from fin_tracker.config import FILE_NAME_BBVA, PATH_RAW_DATA
from fin_tracker.schema import conform_to_schema


def read_bbva_raw(path_file: Path = PATH_RAW_DATA / FILE_NAME_BBVA) -> pd.DataFrame:
    """Read the raw BBVA xlsx extract.

    The sheet has 4 title rows above the header and an empty first column.

    Args:
        path_file: Path to the BBVA xlsx extract.

    Returns:
        Raw BBVA movements with the original Spanish column names.
    """
    return pd.read_excel(path_file, header=4).iloc[:, 1:]


def normalize_bbva(df_bbva_raw: pd.DataFrame) -> pd.DataFrame:
    """Map raw BBVA movements to the unified schema.

    Args:
        df_bbva_raw: Output of :func:`read_bbva_raw`.

    Returns:
        BBVA transactions in the unified schema, oldest first.
    """
    # BBVA lists newest first; reverse so same-day rows stay chronological after sorting
    df_bbva_raw = df_bbva_raw.iloc[::-1].reset_index(drop=True)

    df_bbva = pd.DataFrame(
        {
            "account": "bbva",
            "date": pd.to_datetime(df_bbva_raw["Fecha"], format="%d/%m/%Y"),
            "value_date": pd.to_datetime(df_bbva_raw["F.Valor"], format="%d/%m/%Y"),
            "transaction_type": df_bbva_raw["Movimiento"],
            # Collapse the padding spaces BBVA leaves inside text fields
            "description": df_bbva_raw["Concepto"].str.split().str.join(" "),
            "details": df_bbva_raw["Observaciones"].str.split().str.join(" "),
            "amount": df_bbva_raw["Importe"],
            "currency": df_bbva_raw["Divisa"],
            "amount_eur": df_bbva_raw["Importe"],
            "balance": df_bbva_raw["Disponible"],
            "balance_eur": df_bbva_raw["Disponible"],
        }
    )
    return conform_to_schema(df_bbva)


def load_bbva(path_file: Path = PATH_RAW_DATA / FILE_NAME_BBVA) -> pd.DataFrame:
    """Read and normalize the BBVA extract.

    Args:
        path_file: Path to the BBVA xlsx extract.

    Returns:
        BBVA transactions in the unified schema.
    """
    return normalize_bbva(read_bbva_raw(path_file))
