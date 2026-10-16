"""Personal finance tracker: unify bank extracts and value my net worth."""

from fin_tracker.ingestion import load_all_transactions
from fin_tracker.portfolio import compute_net_worth


def main() -> None:
    """Print a net worth summary built from the raw extracts in ``data/raw``."""
    df_transactions = load_all_transactions()
    dict_results = compute_net_worth(df_transactions)

    df_positions = dict_results["df_positions"]
    df_net_worth = dict_results["df_net_worth"]

    print(
        df_positions[
            ["asset_name", "ticker", "shares", "cost_basis_eur", "market_value_eur"]
        ].to_string(index=False, float_format="{:,.2f}".format)
    )
    print()
    print(df_net_worth.to_string(index=False, float_format="{:,.2f}".format))
    print(f"\nNet worth: {df_net_worth['value_eur'].sum():,.2f} €")
