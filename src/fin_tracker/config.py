"""Project-wide paths and user-specific settings."""

from pathlib import Path


def find_project_root(path_start: Path | None = None) -> Path:
    """Walk up from ``path_start`` until a folder containing ``pyproject.toml`` is found.

    Args:
        path_start: Folder to start searching from. Defaults to this file's folder.

    Returns:
        The project root folder.

    Raises:
        FileNotFoundError: If no ancestor contains a ``pyproject.toml``.
    """
    path_start = path_start or Path(__file__).resolve().parent
    for path_candidate in [path_start, *path_start.parents]:
        if (path_candidate / "pyproject.toml").exists():
            return path_candidate
    raise FileNotFoundError(f"No pyproject.toml found above {path_start}")


PATH_PROJECT_ROOT = find_project_root()
PATH_RAW_DATA = PATH_PROJECT_ROOT / "data" / "raw"
PATH_PROCESSED_DATA = PATH_PROJECT_ROOT / "data" / "processed"

# Raw extract file names, one per bank
FILE_NAME_BBVA = "bbva_full_data.xlsx"
FILE_NAME_REVOLUT = "revolut_full_data.csv"
FILE_NAME_TRADE_REPUBLIC = "tr_full_data.csv"

BASE_CURRENCY = "EUR"

# yfinance cannot always resolve an ISIN, or resolves it to a non-EUR listing.
# Prefer EUR listings (Xetra / BME) so no FX conversion is needed.
ISIN_TO_TICKER_OVERRIDE = {
    "IE00B4L5Y983": "EUNL.DE",  # iShares Core MSCI World, Xetra
    "IE00BKM4GZ66": "IS3N.DE",  # iShares Core MSCI EM IMI, Xetra
    "IE00B4ND3602": "PPFB.DE",  # iShares Physical Gold, Xetra
    "IE000IHURBR0": "29GI.DE",  # iShares iBonds Dec 2029 Term EUR Corp, Xetra
    "IE0000VITHT2": "ID28.L",  # iShares iBonds Dec 2028 Term $ Corp (USD fund)
    "ES0113211835": "BBVA.MC",
    "ES0113900J37": "SAN.MC",
}

# Fraction of each sub-account that belongs to me, used for net worth.
# Unlisted sub-accounts count at 100%.
SUB_ACCOUNT_OWNERSHIP_SHARE = {
    # Shared with partner: money given to it is considered spent, not mine
    "Cuenta Conjunta (EUR)": 0.0,
}

# Trade Republic pays existing clients the ECB deposit facility rate on cash
# (2.50% since 2026-09-16). Update when the ECB moves rates.
TRADE_REPUBLIC_CASH_INTEREST_RATE = 0.025
