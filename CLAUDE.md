# fin_tracker

Personal finance app (Spain, base currency EUR). Unifies bank extracts, values investments, and will support spending tracking, projections and planning.

## Accounts
- **BBVA**: salary account, EUR. xlsx extract, newest first.
- **Revolut**: day-to-day spending. One csv with a table per wallet: personal EUR, FX wallets (HUF/TRY/INR), `Cuenta Conjunta (EUR)` shared with partner, `Round-Up (EUR)` savings.
- **Trade Republic**: investing (ETFs, stocks, bond ETFs with maturities) + cash earning the ECB deposit facility rate.

## Layout
```
src/fin_tracker/
  config.py          paths, ISIN→ticker overrides, ownership shares, TR interest rate
  schema.py          UNIFIED_SCHEMA + conform_to_schema()
  ingestion/         one parser per bank (read_*_raw → normalize_* → load_*), unify.py
  portfolio/         holdings.py (FIFO), market_data.py (yfinance), valuation.py
notebooks/           exploration only; import from fin_tracker, don't duplicate logic
data/raw/            bank extracts (gitignored, never commit)
tests/               pytest, synthetic data only
```

## Commands
- `uv run fin-tracker`: net worth summary
- `uv run pytest`
- `uv run ruff format . && uv run ruff check --fix .`
- After adding modules: `uv sync --reinstall-package fin-tracker`

## Data conventions
- Money uses the cash flow sign: income +, spending/fees/taxes −.
- Revolut `amount` **already includes** fees; `fee`/`tax` are informational. Never add them again.
- Trade Republic `amount` **excludes** `fee` and `tax`; net cash = amount + fee + tax.
- Rows sort by `date, timestamp` with a stable sort; parsers emit rows oldest first so the last `balance` is the current one.
- Cost basis uses FIFO (Spanish tax rule), with fees and taxes included.
- Prefer EUR listings in `ISIN_TO_TICKER_OVERRIDE`. Keep a non-EUR listing only when the fund itself is non-EUR.
- Transfers between my own accounts (BBVA→TR, TR card→Revolut top-ups) are not spending.
- The joint account (`Cuenta Conjunta (EUR)`) is excluded from my finances: ownership share 0, and transfers into it count as spending.

## Code style
- Readable over clever. Descriptive snake_case names, with no abbreviations beyond common ones (`eur`, `fx`, `isin`).
- Type prefixes on variables: `df_`, `series_`, `list_`, `dict_`, `path_`. Module constants are UPPER_SNAKE.
- Google-style docstrings on every public function (Args / Returns / Raises).
- Comments explain *why* or a data quirk, not what the code says.
- Type hints everywhere. ruff config in `pyproject.toml`.
- **Every function gets unit tests.** `tests/` mirrors `src/fin_tracker/` (e.g. `tests/portfolio/test_holdings.py`). Mock network calls (yfinance) and use synthetic data from `tests/conftest.py`.
- Never print or commit real IBANs, card numbers or names in tests/docs; use synthetic data.
