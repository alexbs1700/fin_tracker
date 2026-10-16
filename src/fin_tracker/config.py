"""Project-wide paths and user-specific settings."""

import os
from pathlib import Path

from dotenv import load_dotenv


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
PATH_PRICE_CACHE = PATH_PROCESSED_DATA / "prices"
PATH_CATEGORY_OVERRIDES = PATH_PROCESSED_DATA / "category_overrides.csv"
PATH_CATEGORY_RULES = PATH_PROJECT_ROOT / "config" / "categories.yaml"

# Personal identifiers (my name) live in the gitignored .env, never in the repo
load_dotenv(PATH_PROJECT_ROOT / ".env")
OWNER_NAME = os.environ.get("OWNER_NAME", "")

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

# Broad asset bucket of each ISIN for the allocation view. Unlisted ISINs are equity.
ISIN_TO_ASSET_BUCKET = {
    "IE00B4ND3602": "commodities",  # Physical gold
    "IE000IHURBR0": "fixed_income",  # iBonds Dec 2029
    "IE0000VITHT2": "fixed_income",  # iBonds Dec 2028
}
DEFAULT_ASSET_BUCKET = "equity"

# Fraction of each sub-account that belongs to me, used for net worth.
# Unlisted sub-accounts count at 100%.
JOINT_SUB_ACCOUNT = "Cuenta Conjunta (EUR)"
SUB_ACCOUNT_OWNERSHIP_SHARE = {
    # Shared with partner: money given to it is considered spent, not mine
    JOINT_SUB_ACCOUNT: 0.0,
}

# Internal transfer matching: both legs must have the same EUR amount (within
# the tolerance, wider for FX conversions) and be at most this many days apart
TRANSFER_MATCH_WINDOW_DAYS = 5
TRANSFER_AMOUNT_TOLERANCE_EUR = 0.01
TRANSFER_FX_AMOUNT_TOLERANCE = 0.03
# Round-up conversions of a few cents differ by a cent after rounding
TRANSFER_FX_MIN_TOLERANCE_EUR = 0.05

# Trade Republic pays existing clients the ECB deposit facility rate on cash
# (2.50% since 2026-09-16). Update when the ECB moves rates.
TRADE_REPUBLIC_CASH_INTEREST_RATE = 0.025
