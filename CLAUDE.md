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
  ingestion/         one parser per bank (read_*_raw → normalize_* → load_*), unify.py,
                     banks.py (registry of supported banks), validation.py (upload checks)
  portfolio/         holdings.py (FIFO), market_data.py (yfinance), valuation.py
  categorization/    rules.py (YAML rule engine), transfers.py (leg pairing),
                     overrides.py (manual corrections), pipeline.py
  history/           daily cash, portfolio and net worth series
  projections/       baseline.py (scenario defaults from my data), payroll.py (gross
                     salary calendar → monthly net + June IRPF refund), simulation.py
                     (monthly projection + Monte Carlo percentiles)
  taxes/spain.py     Social Security, IRPF withholding, Madrid IRPF liability (2026 values in config)
  storage/           price_cache.py (yfinance closes/FX cached as CSV)
  api/               FastAPI: store.py (cached dataframes), routes/ (one module per
                     resource), models.py (pydantic), serialization.py
config/categories.yaml  categorization rules (first match wins), user-editable
notebooks/           exploration only; import from fin_tracker, don't duplicate logic
data/raw/            bank extracts (gitignored, never commit)
tests/               pytest, synthetic data only
```

## Commands
- `uv run fin-tracker`: net worth summary
- `uv run fin-tracker-api`: API on http://127.0.0.1:8000 (docs at /docs). It also serves the built app (`npm --prefix frontend run build` → `frontend/dist`) at `/`. `POST /api/reload` after dropping new extracts in `data/raw`.
- New extracts are normally uploaded from the app ("Cargar extractos"): `POST /api/extracts/{bank}/validate` checks, `POST /api/extracts/{bank}` re-validates, backs up the old file to `data/raw/backups/` and replaces it.
- `uv run pytest`
- `uv run ruff format . && uv run ruff check --fix .`
- After adding modules: `uv sync --reinstall-package fin-tracker`
- The real venv is `.venv.nosync` (`.venv` symlinks to it) so iCloud never syncs or hides it.
- Personal identifiers go in `.env` (gitignored, see `.env.example`): `OWNER_NAME` feeds the `{owner_name}` rule placeholder.

## Data conventions
- Money uses the cash flow sign: income +, spending/fees/taxes −.
- Revolut `amount` **already includes** fees; `fee`/`tax` are informational. Never add them again.
- Trade Republic `amount` **excludes** `fee` and `tax`; net cash = amount + fee + tax.
- Rows sort by `date, timestamp` with a stable sort; parsers emit rows oldest first so the last `balance` is the current one.
- Cost basis uses FIFO (Spanish tax rule), with fees and taxes included.
- Prefer EUR listings in `ISIN_TO_TICKER_OVERRIDE`. Keep a non-EUR listing only when the fund itself is non-EUR.
- Every transaction gets a `flow_type`: `internal_transfer`, `investment`, `investment_income`, `income`, `expense`, `excluded`. Only `income`/`expense` count for spending analysis.
- Transfers between my own accounts and wallets (BBVA→Revolut "La pasta del mes", BBVA→TR "Monthly investment", TR card→Revolut, Revolut pockets and FX conversions) are `internal_transfer`, never spending. Both legs share a `transfer_id`; unmatched legs (empty `transfer_id`) need review.
- The joint account (`Cuenta Conjunta (EUR)`) is not mine: ownership share 0, its movements are `excluded`, and my transfers into it are `expense` (category "Cuenta conjunta").
- Buying assets is `investment`: money moves from liquid cash to variable (investments). Net worth is always split into `cash` (liquid) and `investments` (variable).
- `bank_category` is the bank's own label; `category` is ours (rules → manual overrides keyed by `transaction_key`).
- Extract validation: running-balance banks (BBVA, Revolut) must satisfy balance = previous balance + amount on every row (holds 100% on real data); a break means a misread file and blocks the upload. Losing history or wallets only warns. Adding a bank = new parser + entry in `ingestion/banks.py`.
- Spending sums use `amount_eur` (FX wallets report local currency in `amount`).

## Code style
- Readable over clever. Descriptive snake_case names, with no abbreviations beyond common ones (`eur`, `fx`, `isin`).
- Type prefixes on variables: `df_`, `series_`, `list_`, `dict_`, `path_`. Module constants are UPPER_SNAKE.
- Google-style docstrings on every public function (Args / Returns / Raises).
- Comments explain *why* or a data quirk, not what the code says.
- Type hints everywhere. ruff config in `pyproject.toml`.
- **Every function gets unit tests.** `tests/` mirrors `src/fin_tracker/` (e.g. `tests/portfolio/test_holdings.py`). Mock network calls (yfinance) and use synthetic data from `tests/conftest.py`.
- Never print or commit real IBANs, card numbers or names in tests/docs; use synthetic data.

## API
- Endpoints live under `/api`: `net-worth` (+ `/history`, `/history/accounts`), `transactions` (filters, `/summary` with in/out/net per group under the same filters, `/{key}` with transfer counterpart, `PATCH /{key}/category`), `categories`, `cash-flow/monthly`, `portfolio` (+ `/history`), `projections/baseline`, `POST projections/simulate`.
- Route handlers stay thin: aggregation logic goes in plain functions (testable without HTTP) and data comes from `FinanceDataStore`.
- API tests use `tests/api/conftest.py` (`store`, `client`) over the synthetic extracts with faked yfinance.

## Frontend
- React 19 + Vite + TypeScript in `frontend/`; Vite proxies `/api` to the API on :8000. Run the API and `npm --prefix frontend run dev`, open http://127.0.0.1:5173.
- Layout: `src/api/` (types + TanStack Query hooks), `src/lib/` (pure helpers, each with a `*.test.ts`), `src/components/` (ui + Recharts wrappers), `src/pages/` (Resumen, Movimientos, Cartera, Proyecciones).
- Tests: `npm --prefix frontend test` (vitest) and `npm --prefix frontend run typecheck`. Keep logic in `src/lib` so it is unit-tested.
- Movimientos: one set of filters (period, account, multi-select flow types, category, text) drives the table and every summary; inflows use `--series-3`, outflows `--series-4` (same as the Resumen cash flow).
- Look: dark only, black surfaces, white text, minimal (Getquin-like). Tokens live in `src/styles.css`; series colors are the validated dark categorical palette (fixed order, never cycled). Gains/losses always carry sign + arrow, never color alone. Text in Spanish.

## Projections
- Monthly loop: cash earns `cash_return`, investments `investment_return`; net salary, IRPF refund, other income, expenses and the contribution land at month end. Expenses/other income follow inflation and the contribution `investment_growth`, once a year. Rates are annual, nominal, as fractions.
- Salary: a calendar of gross steps (fixed + bonus, from a month), 12 or 14 pays (extras in July and December, bonus in `bonus_month`), `salary_growth` after the last step. Payslips: Social Security 6.5 % on salary + prorated extras (none on the extra pay itself), withholding with the national scale (or a fixed override); the real tax uses state + Madrid scales and settles every June. Matches my real payslip within ~1 %.
- Investing: `investment_mode` is `fixed` (monthly amount growing by `investment_growth`) or `salary_percent` (yearly `investment_plan` of the share of each net payslip invested, extras and bonus included; the last step carries on). The baseline proposes my observed share (invested ÷ net salary, last 12 months).
- IRPF refunds are their own category ("Devolución IRPF") and are excluded from "other income" so they are not counted twice.
- Defaults (`/api/projections/baseline`): averages of the last 12 complete months (extra pays spread over the year), cash yield = TR share of cash × TR rate, return/volatility weighted by asset bucket using `ASSET_BUCKET_EXPECTED_RETURN` / `ASSET_BUCKET_VOLATILITY` in config.
- Monte Carlo: lognormal monthly returns whose mean matches the expected return, fixed seed; the UI shows p10–p90 of the active scenario.
- Tax parameters are 2026 values kept fixed in the future (no bracket deflation). Assumes indefinite contract, under 65, no children, Madrid.
- Not modelled yet: taxes on gains, one-off events (house, car), withdrawals. Scenarios are stored in the browser (localStorage).

## iPhone access (installable web app)
- The built frontend is a PWA (manifest, icons in `frontend/public/icons`, iOS meta tags): Safari → Share → Add to Home Screen. Below 700 px it switches to a bottom tab bar and safe-area padding.
- Network exposure is opt-in: `FIN_TRACKER_HOST=0.0.0.0` in `.env` makes the API reachable on the WiFi. It refuses to start that way without `FIN_TRACKER_ACCESS_KEY` (≥ 12 chars).
- `AccessKeyMiddleware`: every `/api` call from a non-loopback client needs the `X-Access-Key` header (`/api/health` stays public); the Mac itself never needs it. The frontend asks for the key once and keeps it in localStorage.
- Traffic is plain HTTP on the home network; for use outside home, put Tailscale in front rather than opening ports.
