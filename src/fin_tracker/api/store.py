"""In-memory cache of every dataframe the API serves.

Loading the extracts, categorizing and building the daily histories takes a
few seconds, so it is done once per process and reused until ``reload``.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from fin_tracker.categorization import categorize_transactions, save_override
from fin_tracker.config import (
    PATH_CATEGORY_OVERRIDES,
    PATH_CATEGORY_RULES,
    PATH_RAW_DATA,
)
from fin_tracker.history import compute_net_worth_history, compute_portfolio_history
from fin_tracker.ingestion import load_all_transactions
from fin_tracker.portfolio import compute_net_worth


@dataclass
class FinanceDataStore:
    """Lazily computed, cached view of my finances.

    Attributes:
        path_raw_data: Folder with the raw bank extracts.
        path_rules: Categorization rules YAML.
        path_overrides: Manual category overrides CSV.
        dict_placeholders: Rule placeholder values, ``None`` uses ``.env``.
        end_date: Last day of the histories, ``None`` means today.
    """

    path_raw_data: Path = PATH_RAW_DATA
    path_rules: Path = PATH_CATEGORY_RULES
    path_overrides: Path = PATH_CATEGORY_OVERRIDES
    dict_placeholders: dict[str, str] | None = None
    end_date: pd.Timestamp | None = None
    _dict_cache: dict[str, Any] = field(default_factory=dict, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def get_cached(self, name: str, build: Callable[[], Any]) -> Any:
        """Return the cached value ``name``, building it on first access.

        Args:
            name: Cache key.
            build: Function that computes the value.

        Returns:
            The cached value.
        """
        with self._lock:
            if name not in self._dict_cache:
                self._dict_cache[name] = build()
            return self._dict_cache[name]

    @property
    def df_raw_transactions(self) -> pd.DataFrame:
        """Unified transactions straight from the extracts."""
        return self.get_cached(
            "df_raw_transactions", lambda: load_all_transactions(self.path_raw_data)
        )

    @property
    def df_transactions(self) -> pd.DataFrame:
        """Transactions with flow type, category and transfer links."""
        return self.get_cached(
            "df_transactions",
            lambda: categorize_transactions(
                self.df_raw_transactions,
                path_rules=self.path_rules,
                path_overrides=self.path_overrides,
                dict_placeholders=self.dict_placeholders,
            ),
        )

    @property
    def dict_net_worth(self) -> dict[str, pd.DataFrame]:
        """Current snapshot: cash balances, valued positions, realized gains."""
        return self.get_cached(
            "dict_net_worth", lambda: compute_net_worth(self.df_raw_transactions)
        )

    @property
    def df_net_worth_history(self) -> pd.DataFrame:
        """Daily value per account and asset type."""
        return self.get_cached(
            "df_net_worth_history",
            lambda: compute_net_worth_history(self.df_raw_transactions, self.end_date),
        )

    @property
    def df_portfolio_history(self) -> pd.DataFrame:
        """Daily shares, cost basis and value per asset."""
        return self.get_cached(
            "df_portfolio_history",
            lambda: compute_portfolio_history(self.df_raw_transactions, self.end_date),
        )

    def update_category(
        self, transaction_key: str, category: str, flow_type: str | None
    ) -> pd.Series:
        """Store a manual category and refresh the categorized transactions.

        Args:
            transaction_key: Key of the transaction to correct.
            category: New category.
            flow_type: Optional new flow type.

        Returns:
            The updated transaction row.

        Raises:
            KeyError: If no transaction has that key.
        """
        with self._lock:
            is_target = self.df_transactions["transaction_key"] == transaction_key
            if not is_target.any():
                raise KeyError(transaction_key)
            save_override(transaction_key, category, flow_type, self.path_overrides)
            self._dict_cache.pop("df_transactions", None)
            return self.df_transactions[is_target].iloc[0]

    def reload(self) -> None:
        """Forget every cached value so the next request re-reads the extracts."""
        with self._lock:
            self._dict_cache.clear()
