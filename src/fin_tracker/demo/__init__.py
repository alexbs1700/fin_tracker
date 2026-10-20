"""Demo mode: run the whole app on a synthetic persona, offline.

``prepare_demo`` writes made-up extracts to ``data/demo``, routes yfinance to
deterministic price paths and returns a data store isolated from the real
data (its own extracts, price cache and category overrides).
"""

import shutil
from pathlib import Path

import pandas as pd

from fin_tracker.api.store import FinanceDataStore
from fin_tracker.config import PATH_CATEGORY_RULES, PATH_DEMO_DATA
from fin_tracker.demo.extracts import DEMO_OWNER_NAME, write_demo_extracts
from fin_tracker.demo.market import install_demo_market

__all__ = ["DEMO_OWNER_NAME", "prepare_demo"]


def prepare_demo(
    path_demo: Path = PATH_DEMO_DATA, end_date: pd.Timestamp | None = None
) -> FinanceDataStore:
    """Regenerate the demo data and return a store that reads only from it.

    Args:
        path_demo: Folder for the demo extracts, price cache and overrides.
            Its contents are deleted first.
        end_date: Last day of the demo, defaults to today.

    Returns:
        A data store over the demo extracts.
    """
    end_date = end_date or pd.Timestamp.today().normalize()
    shutil.rmtree(path_demo, ignore_errors=True)
    path_raw_data = path_demo / "raw"
    write_demo_extracts(path_raw_data, end_date)
    install_demo_market(path_demo / "prices")
    return FinanceDataStore(
        path_raw_data=path_raw_data,
        path_rules=PATH_CATEGORY_RULES,
        path_overrides=path_demo / "category_overrides.csv",
        dict_placeholders={"owner_name": DEMO_OWNER_NAME},
        end_date=end_date,
    )
