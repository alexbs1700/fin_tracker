"""Spanish gross-to-net payroll: Social Security, IRPF withholding and the yearly return.

Two IRPF numbers matter and they differ:

- The *withholding* (retención) taken from every payslip uses a single
  nationwide scale (RIRPF art. 85), whatever the region.
- The *real tax* is settled in the annual return with the state scale plus
  the regional one. Madrid's is the lowest, so a Madrid resident is usually
  over-withheld and gets a refund in June.

Simplifications: indefinite contract, under 65, no children or dependants,
no disability, and none of the special low-income withholding limits (only
relevant far below the salaries modelled here).
"""

from fin_tracker.config import (
    IRPF_GENERAL_EXPENSES_EUR,
    IRPF_MADRID_SCALE,
    IRPF_PERSONAL_MINIMUM_MADRID_EUR,
    IRPF_PERSONAL_MINIMUM_STATE_EUR,
    IRPF_RETENTION_SCALE,
    IRPF_STATE_SCALE,
    SOCIAL_SECURITY_EMPLOYEE_RATE,
    SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR,
)

# Article 20 LIRPF: reduction for low work income (2025 reform values)
WORK_REDUCTION_FULL_LIMIT_EUR = 14852.0
WORK_REDUCTION_MIDDLE_LIMIT_EUR = 17673.52
WORK_REDUCTION_UPPER_LIMIT_EUR = 19747.5
WORK_REDUCTION_MAXIMUM_EUR = 7302.0
WORK_REDUCTION_MIDDLE_EUR = 2364.34

Scale = list[tuple[float, float]]


def tax_from_scale(base_eur: float, scale: Scale) -> float:
    """Progressive tax of ``base_eur`` under a bracket scale.

    Args:
        base_eur: Taxable amount.
        scale: ``(upper limit, marginal rate)`` pairs in increasing order.

    Returns:
        Tax in EUR.
    """
    tax_eur = 0.0
    lower_limit = 0.0
    for upper_limit, rate in scale:
        if base_eur <= lower_limit:
            break
        tax_eur += (min(base_eur, upper_limit) - lower_limit) * rate
        lower_limit = upper_limit
    return tax_eur


def compute_annual_social_security(annual_gross_eur: float) -> float:
    """Employee Social Security of a year, capped at the maximum contribution base.

    Args:
        annual_gross_eur: Yearly gross pay (all pays and bonus).

    Returns:
        Contribution in EUR.
    """
    capped_base_eur = min(annual_gross_eur, 12 * SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR)
    return SOCIAL_SECURITY_EMPLOYEE_RATE * capped_base_eur


def compute_work_income_reduction(net_work_income_eur: float) -> float:
    """Article 20 LIRPF reduction for low work income.

    Args:
        net_work_income_eur: Gross minus Social Security (before the 2.000 € expenses).

    Returns:
        Reduction in EUR (0 above 19.747,50 €).
    """
    if net_work_income_eur <= WORK_REDUCTION_FULL_LIMIT_EUR:
        return WORK_REDUCTION_MAXIMUM_EUR
    if net_work_income_eur <= WORK_REDUCTION_MIDDLE_LIMIT_EUR:
        return WORK_REDUCTION_MAXIMUM_EUR - 1.75 * (
            net_work_income_eur - WORK_REDUCTION_FULL_LIMIT_EUR
        )
    if net_work_income_eur <= WORK_REDUCTION_UPPER_LIMIT_EUR:
        return WORK_REDUCTION_MIDDLE_EUR - 1.14 * (
            net_work_income_eur - WORK_REDUCTION_MIDDLE_LIMIT_EUR
        )
    return 0.0


def compute_taxable_base(annual_gross_eur: float, social_security_eur: float) -> float:
    """General taxable base of work income: gross, minus Social Security, expenses and reduction.

    Args:
        annual_gross_eur: Yearly gross pay.
        social_security_eur: Employee Social Security paid that year.

    Returns:
        Taxable base in EUR, never negative.
    """
    net_work_income_eur = annual_gross_eur - social_security_eur
    return max(
        0.0,
        net_work_income_eur
        - IRPF_GENERAL_EXPENSES_EUR
        - compute_work_income_reduction(net_work_income_eur),
    )


def compute_retention_rate(annual_gross_eur: float) -> float:
    """IRPF withholding rate the employer applies for an expected yearly gross.

    The withholding scale is applied to the taxable base, minus the same scale
    applied to the personal minimum; the rate is rounded to two decimals of a
    percent, as payroll software does.

    Args:
        annual_gross_eur: Expected yearly gross pay (fixed salary plus bonus).

    Returns:
        Withholding rate as a fraction, e.g. ``0.1822``.
    """
    if annual_gross_eur <= 0:
        return 0.0
    taxable_base_eur = compute_taxable_base(
        annual_gross_eur, compute_annual_social_security(annual_gross_eur)
    )
    withholding_eur = max(
        0.0,
        tax_from_scale(taxable_base_eur, IRPF_RETENTION_SCALE)
        - tax_from_scale(IRPF_PERSONAL_MINIMUM_STATE_EUR, IRPF_RETENTION_SCALE),
    )
    return round(withholding_eur / annual_gross_eur, 4)


def compute_tax_liability(annual_gross_eur: float, social_security_eur: float) -> float:
    """Real IRPF of a year for a Madrid resident (state plus regional scale).

    Args:
        annual_gross_eur: Gross pay actually received that year.
        social_security_eur: Employee Social Security actually paid that year.

    Returns:
        Tax in EUR.
    """
    taxable_base_eur = compute_taxable_base(annual_gross_eur, social_security_eur)
    state_tax_eur = tax_from_scale(taxable_base_eur, IRPF_STATE_SCALE) - tax_from_scale(
        IRPF_PERSONAL_MINIMUM_STATE_EUR, IRPF_STATE_SCALE
    )
    madrid_tax_eur = tax_from_scale(
        taxable_base_eur, IRPF_MADRID_SCALE
    ) - tax_from_scale(IRPF_PERSONAL_MINIMUM_MADRID_EUR, IRPF_MADRID_SCALE)
    return max(0.0, state_tax_eur) + max(0.0, madrid_tax_eur)


def compute_month_payroll(
    month_number: int,
    annual_fixed_gross_eur: float,
    annual_bonus_gross_eur: float,
    payments_per_year: int,
    bonus_month: int,
    extra_pay_months: tuple[int, ...],
    retention_rate: float,
) -> dict[str, float]:
    """Gross, Social Security, withholding and net of one calendar month.

    With 14 pays, Social Security is charged every month on the salary plus a
    twelfth of both extra pays, and nothing on the extra pay itself; that is
    why an extra pay nets more than a regular month. The bonus adds to the
    base of the month it is paid in.

    Args:
        month_number: Calendar month, 1 to 12.
        annual_fixed_gross_eur: Yearly fixed gross salary (all pays).
        annual_bonus_gross_eur: Yearly gross bonus.
        payments_per_year: 12 or 14.
        bonus_month: Calendar month the bonus is paid in.
        extra_pay_months: Calendar months of the two extra pays (14 pays only).
        retention_rate: IRPF withholding rate to apply.

    Returns:
        ``gross_eur``, ``social_security_eur``, ``retention_eur`` and ``net_eur``.
    """
    pay_eur = annual_fixed_gross_eur / payments_per_year
    extra_pays_count = payments_per_year - 12
    gross_eur = pay_eur
    if extra_pays_count and month_number in extra_pay_months:
        gross_eur += pay_eur
    bonus_eur = annual_bonus_gross_eur if month_number == bonus_month else 0.0
    gross_eur += bonus_eur

    # Extra pays are prorated into every month's contribution base
    contribution_base_eur = min(
        pay_eur * (1 + extra_pays_count / 12) + bonus_eur,
        SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR,
    )
    social_security_eur = SOCIAL_SECURITY_EMPLOYEE_RATE * contribution_base_eur
    retention_eur = retention_rate * gross_eur
    return {
        "gross_eur": gross_eur,
        "social_security_eur": social_security_eur,
        "retention_eur": retention_eur,
        "net_eur": gross_eur - social_security_eur - retention_eur,
    }


def estimate_fixed_gross_from_net(
    regular_month_net_eur: float,
    payments_per_year: int,
    annual_bonus_gross_eur: float = 0.0,
) -> float:
    """Yearly fixed gross salary whose regular (non-extra) month nets the given amount.

    Solved by bisection, since withholding depends on the gross itself.

    Args:
        regular_month_net_eur: Net of an ordinary month's payslip.
        payments_per_year: 12 or 14.
        annual_bonus_gross_eur: Yearly gross bonus (it raises the withholding rate).

    Returns:
        Yearly fixed gross in EUR.
    """
    # Any month without extra pay or bonus is a regular month
    regular_month_number = 1
    lower_eur, upper_eur = 0.0, 1_000_000.0
    for _ in range(100):
        middle_eur = (lower_eur + upper_eur) / 2
        net_eur = compute_month_payroll(
            regular_month_number,
            middle_eur,
            annual_bonus_gross_eur,
            payments_per_year,
            bonus_month=0,
            extra_pay_months=(),
            retention_rate=compute_retention_rate(middle_eur + annual_bonus_gross_eur),
        )["net_eur"]
        if net_eur < regular_month_net_eur:
            lower_eur = middle_eur
        else:
            upper_eur = middle_eur
    return round((lower_eur + upper_eur) / 2, 2)
