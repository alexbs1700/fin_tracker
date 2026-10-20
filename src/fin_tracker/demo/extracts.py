"""Synthetic bank extracts for the demo, written in each bank's real file format.

A made-up persona (Madrid, salaried, invests monthly) lives through the last
``DEMO_MONTHS`` months: salary and bills in BBVA, day-to-day spending in
Revolut (with a joint account, round-ups and a trip in HUF) and a savings plan
plus cash interest in Trade Republic. Every internal transfer has both legs,
so the categorization and pairing run exactly as on real data.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

from fin_tracker.config import (
    DEFAULT_BONUS_MONTH,
    FILE_NAME_BBVA,
    FILE_NAME_REVOLUT,
    FILE_NAME_TRADE_REPUBLIC,
    JOINT_SUB_ACCOUNT,
    TRADE_REPUBLIC_CASH_INTEREST_RATE,
)
from fin_tracker.demo.market import DEMO_ASSETS, DEMO_FX_UNITS_PER_EUR, get_price_on
from fin_tracker.projections.payroll import SalaryStep, build_salary_income

DEMO_OWNER_NAME = "Demo User"
DEMO_MONTHS = 20
DEMO_SEED = 2026

PERSONAL_WALLET = "Cuenta personal (EUR)"
HUF_WALLET = "Cuenta personal (HUF)"
ROUND_UP_WALLET = "Round-Up (EUR)"

OPENING_BALANCE_BBVA_EUR = 11000.0
OPENING_BALANCE_PERSONAL_EUR = 600.0
OPENING_TRANSFER_TO_TRADE_REPUBLIC_EUR = 5000.0
OPENING_STOCK_PURCHASE_EUR = 1500.0

RENT_EUR = 950.0
MONTHLY_SPENDING_TRANSFER_EUR = 950.0
JOINT_CONTRIBUTION_EUR = 350.0
# Monthly investment before and after the raise
MONTHLY_INVESTMENT_EUR = (700.0, 900.0)
# Yearly gross before and after the raise, 14 payments; the bonus starts with the raise
GROSS_SALARY_EUR = (46000.0, 52000.0)
RAISE_BONUS_EUR = 4000.0
# Months (counted from the first demo month) of the raise and of the two trips
RAISE_MONTH_INDEX = 10
BUDAPEST_TRIP_MONTH_INDEX = 5
DOMESTIC_TRIP_MONTH_INDEX = 14
SAVINGS_PLAN_WEIGHTS = {
    "IE00DEMO0001": 0.65,
    "IE00DEMO0002": 0.15,
    "IE00DEMO0003": 0.20,
}
DIVIDEND_STOCK_ISIN = "ES00DEMO0004"
DIVIDEND_PER_SHARE_EUR = 0.18
DIVIDEND_MONTHS = (3, 6, 9, 12)
SPANISH_DIVIDEND_TAX_RATE = 0.19

# (description, min EUR, max EUR, times per month) of card spending in Revolut
REVOLUT_CARD_SPENDING = [
    ("Mercadona", 18.0, 65.0, 4),
    ("Lidl", 12.0, 40.0, 2),
    ("Fruteria Lavapies", 6.0, 18.0, 1),
    ("Restaurante La Tasca", 18.0, 45.0, 2),
    ("Goiko", 14.0, 28.0, 1),
    ("Starbucks", 4.5, 9.0, 2),
    ("Glovo", 15.0, 30.0, 1),
    ("Cabify", 8.0, 19.0, 2),
    ("Farmacia Sol", 6.0, 25.0, 1),
    ("Amazon", 15.0, 80.0, 1),
    ("Cine Yelmo", 9.0, 18.0, 1),
]
# (description, EUR, day of month) charged every month in Revolut
REVOLUT_FIXED_SPENDING = [
    ("Gimnasio Fitness Park", 39.90, 3),
    ("Consorcio Regional de Transportes abono", 20.0, 4),
    ("Spotify", 11.99, 10),
    ("Netflix", 13.99, 15),
]
JOINT_SPENDING = [
    ("Mercadona", 45.0, 110.0, 5),
    ("Restaurante El Patio", 30.0, 70.0, 1),
    ("Ikea", 20.0, 120.0, 1),
]
BBVA_BILLS = [
    ("Recibo Iberdrola luz", 35.0, 85.0, 6),
    ("Recibo Digi fibra y movil", 25.0, 25.0, 8),
]
TRADE_REPUBLIC_CARD_SPENDING = [
    ("Cafe Comercial", 5812, 6.0, 22.0),
    ("Decathlon", 5941, 20.0, 90.0),
]
SPANISH_MONTH_ABBREVIATIONS = [
    "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sept", "oct", "nov", "dic",
]  # fmt: skip


@dataclass
class DemoLedger:
    """Movements of every account, in each bank's own vocabulary."""

    list_bbva: list[dict] = field(default_factory=list)
    dict_revolut: dict[str, list[dict]] = field(default_factory=dict)
    list_trade_republic: list[dict] = field(default_factory=list)

    def add_bbva(
        self, date: pd.Timestamp, description: str, amount: float, movement: str
    ) -> None:
        """Add a BBVA movement."""
        self.list_bbva.append(
            {
                "date": date,
                "description": description,
                "amount": round(amount, 2),
                "movement": movement,
            }
        )

    def add_revolut(
        self,
        wallet: str,
        date: pd.Timestamp,
        description: str,
        amount: float,
        bank_category: str,
        fee: float = 0.0,
        amount_eur: float | None = None,
    ) -> None:
        """Add a Revolut movement; ``amount`` is in the wallet's currency."""
        self.dict_revolut.setdefault(wallet, []).append(
            {
                "date": date,
                "description": description,
                "bank_category": bank_category,
                "amount": round(amount, 2),
                "amount_eur": round(amount if amount_eur is None else amount_eur, 2),
                "fee": fee,
            }
        )

    def add_trade_republic(self, date: pd.Timestamp, hour: int, **dict_columns) -> None:
        """Add a Trade Republic row; ``dict_columns`` are raw csv columns."""
        self.list_trade_republic.append(
            {
                "datetime": f"{date:%Y-%m-%d}T{hour:02d}:00:00Z",
                "date": f"{date:%Y-%m-%d}",
                **dict_columns,
            }
        )


def get_demo_months(end_date: pd.Timestamp) -> list[pd.Period]:
    """The ``DEMO_MONTHS`` calendar months ending with the month of ``end_date``."""
    last_month = end_date.to_period("M")
    return list(pd.period_range(last_month - (DEMO_MONTHS - 1), last_month, freq="M"))


def compute_salary_by_month(list_months: list[pd.Period]) -> pd.DataFrame:
    """Net payslip and June IRPF refund of every demo month, from the payroll model.

    Using the real payroll rules means the Proyecciones page inverts the
    demo payslips back to the same gross salary.

    Args:
        list_months: Demo months.

    Returns:
        One row per month (``YYYY-MM``) with ``salary_net_eur`` and ``tax_refund_eur``.
    """
    salary_schedule = (
        SalaryStep(str(list_months[0]), GROSS_SALARY_EUR[0]),
        SalaryStep(
            str(list_months[RAISE_MONTH_INDEX]), GROSS_SALARY_EUR[1], RAISE_BONUS_EUR
        ),
    )
    # Start a year early so the first June already has last year's refund
    list_payroll_months = [
        str(month)
        for month in pd.period_range(
            f"{list_months[0].year - 1}-01", list_months[-1], freq="M"
        )
    ]
    df_income, _ = build_salary_income(
        salary_schedule, 0.0, 14, DEFAULT_BONUS_MONTH, None, list_payroll_months
    )
    return df_income.set_index("month").loc[[str(month) for month in list_months]]


def get_day(month: pd.Period, day: int) -> pd.Timestamp:
    """Day ``day`` of ``month``, clipped to the month's length."""
    return month.start_time + pd.Timedelta(days=min(day, month.days_in_month) - 1)


def get_last_business_day(month: pd.Period) -> pd.Timestamp:
    """Last Monday to Friday of ``month``."""
    return pd.offsets.BMonthEnd().rollforward(month.start_time)


def draw_amount(
    rng: np.random.Generator, minimum_eur: float, maximum_eur: float
) -> float:
    """Random amount between two bounds, rounded to cents."""
    return round(float(rng.uniform(minimum_eur, maximum_eur)), 2)


def add_savings_plan(ledger: DemoLedger, date: pd.Timestamp, amount_eur: float) -> None:
    """Buy the savings plan funds for ``amount_eur`` at that day's closes, free of fees."""
    for isin, weight in SAVINGS_PLAN_WEIGHTS.items():
        price_eur = get_price_on(isin, date)
        amount_asset_eur = round(amount_eur * weight, 2)
        ledger.add_trade_republic(
            date, 9, category="TRADING", type="BUY", asset_class=DEMO_ASSETS[isin].asset_class,
            name=DEMO_ASSETS[isin].name, symbol=isin, shares=round(amount_asset_eur / price_eur, 6),
            price=price_eur, amount=-amount_asset_eur, description="Savings plan execution",
        )  # fmt: skip


def add_opening_movements(ledger: DemoLedger, first_day: pd.Timestamp) -> None:
    """Move savings to Trade Republic and buy the dividend stock on the first day."""
    ledger.add_bbva(
        first_day, f"Traspaso a {DEMO_OWNER_NAME}",
        -OPENING_TRANSFER_TO_TRADE_REPUBLIC_EUR, "Transferencia realizada",
    )  # fmt: skip
    ledger.add_trade_republic(
        first_day, 8, category="CASH", type="TRANSFER_INBOUND",
        amount=OPENING_TRANSFER_TO_TRADE_REPUBLIC_EUR, counterparty_name=DEMO_OWNER_NAME,
        description=f"Incoming transfer from {DEMO_OWNER_NAME}",
    )  # fmt: skip
    stock = DEMO_ASSETS[DIVIDEND_STOCK_ISIN]
    price_eur = get_price_on(DIVIDEND_STOCK_ISIN, first_day)
    shares = float(np.floor(OPENING_STOCK_PURCHASE_EUR / price_eur))
    ledger.add_trade_republic(
        first_day, 10, category="TRADING", type="BUY", asset_class=stock.asset_class,
        name=stock.name, symbol=DIVIDEND_STOCK_ISIN, shares=shares, price=price_eur,
        amount=-round(shares * price_eur, 2), fee=-1.0, description="Buy trade",
    )  # fmt: skip


def add_bbva_month(
    ledger: DemoLedger,
    month: pd.Period,
    rng: np.random.Generator,
    salary_net_eur: float,
    tax_refund_eur: float,
    investment_eur: float,
) -> None:
    """Rent, transfers to Revolut and Trade Republic, bills, salary and IRPF refund."""
    ledger.add_bbva(
        get_day(month, 1),
        "Alquiler piso Calle Demo",
        -RENT_EUR,
        "Transferencia realizada",
    )
    ledger.add_bbva(
        get_day(month, 1),
        "La pasta del mes",
        -MONTHLY_SPENDING_TRANSFER_EUR,
        "Transferencia realizada",
    )
    ledger.add_bbva(
        get_day(month, 2),
        "Monthly investment",
        -investment_eur,
        "Transferencia realizada",
    )
    for description, minimum_eur, maximum_eur, day in BBVA_BILLS:
        ledger.add_bbva(
            get_day(month, day),
            description,
            -draw_amount(rng, minimum_eur, maximum_eur),
            "Adeudo recibo",
        )
    if month.month % 4 == 0:
        ledger.add_bbva(
            get_day(month, 20),
            "El Corte Ingles",
            -draw_amount(rng, 60.0, 220.0),
            "Pago con tarjeta",
        )
    if tax_refund_eur > 0:
        ledger.add_bbva(
            get_day(month, 26),
            "Devolucion AEAT IRPF",
            tax_refund_eur,
            "Transferencia recibida",
        )
    ledger.add_bbva(get_last_business_day(month), "Nomina Demo Empresa SL", salary_net_eur, "Abono de nómina")  # fmt: skip


def add_revolut_month(
    ledger: DemoLedger, month: pd.Period, month_index: int, rng: np.random.Generator
) -> None:
    """Top-up from BBVA, card spending, joint account, round-ups and trips."""
    ledger.add_revolut(
        PERSONAL_WALLET,
        get_day(month, 1),
        f"Transferencia de {DEMO_OWNER_NAME}",
        MONTHLY_SPENDING_TRANSFER_EUR,
        "Transferencias",
    )
    ledger.add_revolut(
        PERSONAL_WALLET,
        get_day(month, 2),
        "Transferencia a Demo & Partner",
        -JOINT_CONTRIBUTION_EUR,
        "Transferencias",
    )
    ledger.add_revolut(
        JOINT_SUB_ACCOUNT,
        get_day(month, 2),
        f"Transferencia de {DEMO_OWNER_NAME}",
        JOINT_CONTRIBUTION_EUR,
        "Transferencias",
    )
    ledger.add_revolut(
        JOINT_SUB_ACCOUNT,
        get_day(month, 2),
        "Transferencia de Partner",
        JOINT_CONTRIBUTION_EUR,
        "Transferencias",
    )
    ledger.add_revolut(PERSONAL_WALLET, get_day(month, 7), "Tarifa del plan Premium", -8.99, "Comercio", fee=8.99)  # fmt: skip

    list_dated_spending = [
        (description, -amount_eur, day)
        for description, amount_eur, day in REVOLUT_FIXED_SPENDING
    ] + [
        (
            description,
            -draw_amount(rng, minimum_eur, maximum_eur),
            int(rng.integers(3, 29)),
        )
        for description, minimum_eur, maximum_eur, times in REVOLUT_CARD_SPENDING
        for _ in range(times)
    ]
    list_dated_spending.append(
        ("Bizum payment to Ana", -float(rng.integers(8, 30)), int(rng.integers(5, 28)))
    )
    list_dated_spending.append(("Bizum recibido de Luis", float(rng.integers(8, 25)), int(rng.integers(5, 28))))  # fmt: skip
    for description, amount_eur, day in sorted(
        list_dated_spending, key=lambda item: item[2]
    ):
        ledger.add_revolut(
            PERSONAL_WALLET, get_day(month, day), description, amount_eur, "Compras"
        )

    for description, minimum_eur, maximum_eur, times in JOINT_SPENDING:
        for _ in range(times):
            day = int(rng.integers(3, 29))
            ledger.add_revolut(
                JOINT_SUB_ACCOUNT,
                get_day(month, day),
                description,
                -draw_amount(rng, minimum_eur, maximum_eur),
                "Compras",
            )

    for day in (7, 14, 21, 28):
        round_up_eur = draw_amount(rng, 1.5, 6.0)
        ledger.add_revolut(
            PERSONAL_WALLET,
            get_day(month, day),
            "Round-up a pocket",
            -round_up_eur,
            "Transferencias",
        )
        ledger.add_revolut(ROUND_UP_WALLET, get_day(month, day), "Round-up desde Cuenta personal", round_up_eur, "Transferencias")  # fmt: skip

    if month_index == BUDAPEST_TRIP_MONTH_INDEX:
        add_budapest_trip(ledger, month, rng)
    if month_index == DOMESTIC_TRIP_MONTH_INDEX:
        ledger.add_revolut(
            PERSONAL_WALLET, get_day(month, 8), "Renfe Viajeros", -64.30, "Transporte"
        )
        ledger.add_revolut(
            PERSONAL_WALLET, get_day(month, 9), "Airbnb Sevilla", -240.0, "Viajes"
        )


def add_budapest_trip(
    ledger: DemoLedger, month: pd.Period, rng: np.random.Generator
) -> None:
    """Flights and hotel in EUR, then a conversion to HUF spent in the HUF wallet."""
    huf_per_eur = DEMO_FX_UNITS_PER_EUR["EURHUF=X"]
    ledger.add_revolut(PERSONAL_WALLET, get_day(month, 4), "Ryanair", -118.40, "Viajes")
    ledger.add_revolut(
        PERSONAL_WALLET, get_day(month, 5), "Booking.com Budapest", -265.0, "Viajes"
    )
    conversion_eur = 250.0
    ledger.add_revolut(
        PERSONAL_WALLET,
        get_day(month, 12),
        "Conversión a HUF",
        -conversion_eur,
        "Cambio",
    )
    ledger.add_revolut(HUF_WALLET, get_day(month, 12), "Conversión a HUF", conversion_eur * huf_per_eur, "Cambio", amount_eur=conversion_eur)  # fmt: skip
    for day, description in [
        (12, "Budapest Bistro"),
        (13, "BKK Budapest transport"),
        (13, "Szimpla Kert bar"),
        (14, "Great Market Hall"),
    ]:
        amount_huf = float(rng.integers(30, 46)) * 500
        ledger.add_revolut(HUF_WALLET, get_day(month, day), description, -amount_huf, "Viajes", amount_eur=-amount_huf / huf_per_eur)  # fmt: skip


def add_trade_republic_month(
    ledger: DemoLedger,
    month: pd.Period,
    rng: np.random.Generator,
    investment_eur: float,
    cash_eur: float,
) -> float:
    """Incoming transfer, savings plan, card use, dividends and interest.

    Args:
        ledger: Ledger to add to.
        month: Calendar month.
        rng: Random generator of the month.
        investment_eur: Amount transferred from BBVA and invested.
        cash_eur: Trade Republic cash at the start of the month, for the interest.

    Returns:
        Cash at the end of the month.
    """
    day_transfer = get_day(month, 2)
    ledger.add_trade_republic(
        day_transfer, 8, category="CASH", type="TRANSFER_INBOUND", amount=investment_eur,
        counterparty_name=DEMO_OWNER_NAME, description=f"Incoming transfer from {DEMO_OWNER_NAME}",
    )  # fmt: skip
    add_savings_plan(ledger, get_day(month, 3), investment_eur)
    cash_eur += investment_eur - sum(
        round(investment_eur * weight, 2) for weight in SAVINGS_PLAN_WEIGHTS.values()
    )

    for merchant, mcc_code, minimum_eur, maximum_eur in TRADE_REPUBLIC_CARD_SPENDING:
        amount_eur = draw_amount(rng, minimum_eur, maximum_eur)
        ledger.add_trade_republic(
            get_day(month, int(rng.integers(5, 26))), 13, category="CASH", type="CARD_TRANSACTION",
            name=merchant, amount=-amount_eur, mcc_code=mcc_code, description=merchant,
        )  # fmt: skip
        cash_eur -= amount_eur

    if month.month in DIVIDEND_MONTHS:
        shares = sum(
            row["shares"] for row in ledger.list_trade_republic
            if row.get("symbol") == DIVIDEND_STOCK_ISIN and row["type"] == "BUY"
        )  # fmt: skip
        dividend_eur = round(shares * DIVIDEND_PER_SHARE_EUR, 2)
        tax_eur = -round(dividend_eur * SPANISH_DIVIDEND_TAX_RATE, 2)
        stock = DEMO_ASSETS[DIVIDEND_STOCK_ISIN]
        ledger.add_trade_republic(
            get_day(month, 15), 7, category="CASH", type="DIVIDEND", asset_class=stock.asset_class,
            name=stock.name, symbol=DIVIDEND_STOCK_ISIN, shares=shares, amount=dividend_eur,
            tax=tax_eur, description="Cash Dividend",
        )  # fmt: skip
        cash_eur += dividend_eur + tax_eur

    interest_eur = round(cash_eur * TRADE_REPUBLIC_CASH_INTEREST_RATE / 12, 2)
    ledger.add_trade_republic(
        get_day(month, 31), 6, category="CASH", type="INTEREST_PAYMENT",
        amount=interest_eur, description="Interest payment",
    )  # fmt: skip
    return cash_eur + interest_eur


def build_demo_ledger(end_date: pd.Timestamp) -> DemoLedger:
    """Every demo movement from the first demo month up to ``end_date``.

    Args:
        end_date: Last day with movements (usually today).

    Returns:
        The ledger, with movements after ``end_date`` dropped.
    """
    list_months = get_demo_months(end_date)
    df_salary = compute_salary_by_month(list_months)
    ledger = DemoLedger()
    add_opening_movements(ledger, list_months[0].start_time)
    cash_trade_republic_eur = OPENING_TRANSFER_TO_TRADE_REPUBLIC_EUR - sum(
        -row["amount"] - row.get("fee", 0.0) for row in ledger.list_trade_republic if row["type"] == "BUY"
    )  # fmt: skip

    for month_index, month in enumerate(list_months):
        # One generator per month, so a month looks the same whatever the end date
        rng = np.random.default_rng([DEMO_SEED, month.year, month.month])
        investment_eur = MONTHLY_INVESTMENT_EUR[month_index >= RAISE_MONTH_INDEX]
        add_bbva_month(
            ledger, month, rng,
            float(df_salary.loc[str(month), "salary_net_eur"]),
            float(df_salary.loc[str(month), "tax_refund_eur"]),
            investment_eur,
        )  # fmt: skip
        add_revolut_month(ledger, month, month_index, rng)
        cash_trade_republic_eur = add_trade_republic_month(
            ledger, month, rng, investment_eur, cash_trade_republic_eur
        )

    ledger.list_bbva = [row for row in ledger.list_bbva if row["date"] <= end_date]
    ledger.dict_revolut = {
        wallet: [row for row in list_rows if row["date"] <= end_date]
        for wallet, list_rows in ledger.dict_revolut.items()
    }
    ledger.list_trade_republic = [
        row
        for row in ledger.list_trade_republic
        if pd.Timestamp(row["date"]) <= end_date
    ]
    return ledger


def with_running_balance(
    list_rows: list[dict], opening_balance: float, amount_key: str = "amount"
) -> list[dict]:
    """Rows sorted by date (stable) with the balance after each one."""
    list_sorted = sorted(list_rows, key=lambda row: row["date"])
    balance = opening_balance
    for row in list_sorted:
        balance = round(balance + row[amount_key], 2)
        row[f"balance_{amount_key}"] = balance
    return list_sorted


def write_bbva_extract(list_rows: list[dict], path_file: Path) -> None:
    """Write BBVA movements as BBVA's xlsx: 4 title rows, header, newest first.

    Args:
        list_rows: ``DemoLedger.list_bbva``.
        path_file: Target xlsx.
    """
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    for title in [
        "Últimos movimientos",
        "Cuenta ES00 0000 0000 0000 0000 0000",
        "Demo",
        "",
    ]:
        worksheet.append([title])
    worksheet.append([None, "F.Valor", "Fecha", "Concepto", "Movimiento", "Importe", "Divisa", "Disponible", "Divisa", "Observaciones"])  # fmt: skip
    for row in reversed(with_running_balance(list_rows, OPENING_BALANCE_BBVA_EUR)):
        day = f"{row['date']:%d/%m/%Y}"
        worksheet.append([None, day, day, row["description"], row["movement"], row["amount"], "EUR", row["balance_amount"], "EUR", row["description"].upper()])  # fmt: skip
    workbook.save(path_file)


def format_spanish_money(amount: float, currency: str) -> str:
    """Format like Revolut's Spanish export: ``"-1.234,56€"`` or ``"4.000,00 HUF"``."""
    text = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text}€" if currency == "EUR" else f"{text} {currency}"


def format_spanish_date(date: pd.Timestamp) -> str:
    """Format like Revolut's Spanish export, e.g. ``"7 sept 2025"``."""
    return f"{date.day} {SPANISH_MONTH_ABBREVIATIONS[date.month - 1]} {date.year}"


def build_revolut_wallet_lines(
    wallet: str, list_rows: list[dict], opening_balance: float
) -> list[str]:
    """Transaction table of one wallet, in the EUR or foreign currency layout."""
    currency = wallet[-4:-1]
    list_lines = [
        f'"{wallet}",,,,,,,,',
        ",,,,,,,,",
        '"Extracto de transacción",,,,,,,,',
    ]
    if not list_rows:
        return [*list_lines, "---------,,,,,,,,"]

    def quote(amount: float, money_currency: str) -> str:
        return f'"{format_spanish_money(amount, money_currency)}"'

    list_sorted = with_running_balance(list_rows, opening_balance)
    if currency == "EUR":
        list_lines.append('Fecha,Descripción,Categoría,"Entradas/salidas de dinero",Saldo,"Impuestos retenidos","Otros impuestos",Comisiones')  # fmt: skip
        for row in list_sorted:
            list_lines.append(
                f'"{format_spanish_date(row["date"])}","{row["description"]}",{row["bank_category"]},'
                f"{quote(row['amount'], 'EUR')},{quote(row['balance_amount'], 'EUR')},"
                f"{quote(0, 'EUR')},{quote(0, 'EUR')},{quote(row['fee'], 'EUR')}"
            )
    else:
        with_running_balance(list_sorted, 0.0, amount_key="amount_eur")
        list_lines.append(
            'Fecha,Descripción,Categoría,"Entradas/salidas de dinero","Entradas/salidas de dinero",'
            'Saldo,Saldo,"Impuestos retenidos","Impuestos retenidos","Otros impuestos","Otros impuestos",'
            "Comisiones,Comisiones"
        )
        for row in list_sorted:
            list_lines.append(
                f'"{format_spanish_date(row["date"])}","{row["description"]}",{row["bank_category"]},'
                f"{quote(row['amount'], currency)},{quote(row['amount_eur'], 'EUR')},"
                f"{quote(row['balance_amount'], currency)},{quote(row['balance_amount_eur'], 'EUR')},"
                + ",".join([quote(0, currency), quote(0, "EUR")] * 3)
            )
    total = sum(row["amount"] for row in list_sorted)
    return [*list_lines, f"Total,,,{quote(total, currency)},,,,,", ",,,,,,,,"]


def write_revolut_extract(
    dict_wallet_rows: dict[str, list[dict]], path_file: Path
) -> None:
    """Write Revolut movements as its Spanish csv, one table per wallet.

    Args:
        dict_wallet_rows: ``DemoLedger.dict_revolut``.
        path_file: Target csv.
    """
    dict_opening_balances = {PERSONAL_WALLET: OPENING_BALANCE_PERSONAL_EUR}
    list_lines = ['"Cuentas corrientes Estado de transacciones",,,,,,,,', ",,,,,,,,"]
    for wallet in [PERSONAL_WALLET, HUF_WALLET, JOINT_SUB_ACCOUNT, ROUND_UP_WALLET]:
        list_lines += build_revolut_wallet_lines(
            wallet,
            dict_wallet_rows.get(wallet, []),
            dict_opening_balances.get(wallet, 0.0),
        )
    path_file.write_text("\n".join(list_lines), encoding="utf-8")


TRADE_REPUBLIC_COLUMNS = [
    "datetime", "date", "account_type", "category", "type", "asset_class", "name",
    "symbol", "shares", "price", "amount", "fee", "tax", "currency", "original_amount",
    "original_currency", "fx_rate", "description", "transaction_id", "counterparty_name",
    "counterparty_iban", "payment_reference", "mcc_code",
]  # fmt: skip


def write_trade_republic_extract(list_rows: list[dict], path_file: Path) -> None:
    """Write Trade Republic movements as its csv export, oldest first.

    Args:
        list_rows: ``DemoLedger.list_trade_republic``.
        path_file: Target csv.
    """
    df_tr_raw = (
        pd.DataFrame(list_rows)
        .reindex(columns=TRADE_REPUBLIC_COLUMNS)
        .sort_values("datetime", kind="stable")
        .reset_index(drop=True)
    )
    df_tr_raw["account_type"] = "DEFAULT"
    df_tr_raw["currency"] = "EUR"
    df_tr_raw["transaction_id"] = [
        f"demo-{index:05d}" for index in range(len(df_tr_raw))
    ]
    df_tr_raw.to_csv(path_file, index=False)


def write_demo_extracts(path_raw_data: Path, end_date: pd.Timestamp) -> DemoLedger:
    """Generate the demo ledger and write the three extracts into ``path_raw_data``.

    Args:
        path_raw_data: Folder for the extracts (created if missing).
        end_date: Last day with movements.

    Returns:
        The ledger that was written.
    """
    path_raw_data.mkdir(parents=True, exist_ok=True)
    ledger = build_demo_ledger(end_date)
    write_bbva_extract(ledger.list_bbva, path_raw_data / FILE_NAME_BBVA)
    write_revolut_extract(ledger.dict_revolut, path_raw_data / FILE_NAME_REVOLUT)
    write_trade_republic_extract(
        ledger.list_trade_republic, path_raw_data / FILE_NAME_TRADE_REPUBLIC
    )
    return ledger
