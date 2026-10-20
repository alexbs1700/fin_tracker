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
# Network exposure of the API. Loopback by default; any other host (e.g. 0.0.0.0
# to reach it from the iPhone on the home WiFi) requires an access key.
API_HOST = os.environ.get("FIN_TRACKER_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("FIN_TRACKER_PORT", "8000"))
API_ACCESS_KEY = os.environ.get("FIN_TRACKER_ACCESS_KEY", "")
PATH_FRONTEND_DIST = PATH_PROJECT_ROOT / "frontend" / "dist"

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

# Projection assumptions: long-run nominal annual return and volatility per asset
# bucket (rough historical figures for diversified global funds, not forecasts).
# They only seed the defaults of the Proyecciones page; every scenario can override them.
ASSET_BUCKET_EXPECTED_RETURN = {
    "equity": 0.07,
    "fixed_income": 0.03,
    "commodities": 0.04,
}
ASSET_BUCKET_VOLATILITY = {"equity": 0.16, "fixed_income": 0.05, "commodities": 0.15}
DEFAULT_INFLATION = 0.025  # ECB target is 2 %, Spanish CPI has run slightly above
DEFAULT_SALARY_GROWTH = 0.03
# Months of history used to estimate monthly salary, expenses and investing
PROJECTION_LOOKBACK_MONTHS = 12

# Spanish payroll and IRPF parameters for 2026 (Madrid resident, indefinite contract).
# Sources: Orden PJC/297/2026 (BOE) for Social Security; LIRPF arts. 19, 20, 57, 63
# and 101 / RIRPF art. 85 for IRPF; Ley 13/2023 de la Comunidad de Madrid for its scale.
# Kept fixed for future years: Spain rarely deflates brackets (fiscal drag is realistic).
SOCIAL_SECURITY_EMPLOYEE_RATE = 0.065  # 4.70 CC + 1.55 desempleo + 0.10 FP + 0.15 MEI
SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR = 5101.20
IRPF_GENERAL_EXPENSES_EUR = 2000.0
IRPF_PERSONAL_MINIMUM_STATE_EUR = 5550.0
IRPF_PERSONAL_MINIMUM_MADRID_EUR = 5956.65
# (upper limit of the bracket, marginal rate); the last bracket has no upper limit
IRPF_RETENTION_SCALE = [
    (12450.0, 0.19), (20200.0, 0.24), (35200.0, 0.30),
    (60000.0, 0.37), (300000.0, 0.45), (float("inf"), 0.47),
]  # fmt: skip
IRPF_STATE_SCALE = [
    (12450.0, 0.095), (20200.0, 0.12), (35200.0, 0.15),
    (60000.0, 0.185), (300000.0, 0.225), (float("inf"), 0.245),
]  # fmt: skip
IRPF_MADRID_SCALE = [
    (13362.22, 0.085), (19004.63, 0.107), (35425.68, 0.128),
    (57320.40, 0.174), (float("inf"), 0.205),
]  # fmt: skip
# My payroll: the two extra pays arrive in July and December, the bonus in July
EXTRA_PAY_MONTHS = (7, 12)
DEFAULT_BONUS_MONTH = 7
TAX_REFUND_MONTH = 6  # The annual IRPF return settles in June of the next year
