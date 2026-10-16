"""Tests for fin_tracker.taxes.spain.

Reference figures: 35.500 € gross, indefinite contract, Madrid, no children
(checked by hand against the published 2026 scales), and my real payslip:
1.882 € a regular month and 2.073,71 € each extra pay with ~35.400 € fixed.
"""

import pytest

from fin_tracker.config import (
    IRPF_RETENTION_SCALE,
    SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR,
)
from fin_tracker.taxes.spain import (
    compute_annual_social_security,
    compute_month_payroll,
    compute_retention_rate,
    compute_tax_liability,
    compute_taxable_base,
    compute_work_income_reduction,
    estimate_fixed_gross_from_net,
    tax_from_scale,
)


def test_tax_from_scale_is_progressive():
    assert tax_from_scale(0, IRPF_RETENTION_SCALE) == 0
    assert tax_from_scale(10000, IRPF_RETENTION_SCALE) == pytest.approx(1900)
    # 12.450 at 19 % + 7.550 at 24 %
    assert tax_from_scale(20000, IRPF_RETENTION_SCALE) == pytest.approx(2365.5 + 1812)


def test_compute_annual_social_security_is_capped():
    assert compute_annual_social_security(35500) == pytest.approx(2307.5)
    assert compute_annual_social_security(200000) == pytest.approx(
        0.065 * 12 * SOCIAL_SECURITY_MAX_MONTHLY_BASE_EUR
    )


@pytest.mark.parametrize(
    ("net_work_income_eur", "expected_reduction_eur"),
    [
        (10000, 7302),
        (16000, 7302 - 1.75 * 1148),
        (18000, 2364.34 - 1.14 * 326.48),
        (25000, 0),
    ],
)
def test_compute_work_income_reduction(net_work_income_eur, expected_reduction_eur):
    assert compute_work_income_reduction(net_work_income_eur) == pytest.approx(
        expected_reduction_eur
    )


def test_compute_taxable_base():
    assert compute_taxable_base(35500, 2307.5) == pytest.approx(31192.5)
    assert compute_taxable_base(5000, 325) == 0


def test_compute_retention_rate_reference_salary():
    assert compute_retention_rate(35500) == pytest.approx(0.1822)
    assert compute_retention_rate(0) == 0
    # Low salaries: the personal minimum and the reduction leave nothing to withhold
    assert compute_retention_rate(12000) == 0


def test_compute_tax_liability_madrid_is_below_withholding():
    liability_eur = compute_tax_liability(35500, 2307.5)
    assert liability_eur == pytest.approx(6027.63, abs=0.05)
    assert liability_eur < 0.1822 * 35500


def test_compute_month_payroll_matches_my_payslip():
    rate = compute_retention_rate(35393)
    regular = compute_month_payroll(1, 35393, 0, 14, 7, (7, 12), rate)
    extra = compute_month_payroll(12, 35393, 0, 14, 7, (7, 12), rate)

    assert regular["net_eur"] == pytest.approx(1882, rel=0.01)
    # Extra pay months carry no extra Social Security
    assert extra["social_security_eur"] == regular["social_security_eur"]
    assert extra["net_eur"] - regular["net_eur"] == pytest.approx(2073.71, rel=0.01)


def test_compute_month_payroll_bonus_and_twelve_pays():
    with_bonus = compute_month_payroll(7, 36000, 3000, 12, 7, (7, 12), 0.2)
    assert with_bonus["gross_eur"] == pytest.approx(3000 + 3000)
    assert with_bonus["social_security_eur"] == pytest.approx(0.065 * 5101.20)
    assert with_bonus["retention_eur"] == pytest.approx(1200)


def test_estimate_fixed_gross_from_net_inverts_the_payslip():
    fixed_gross_eur = estimate_fixed_gross_from_net(1882, 14)
    rate = compute_retention_rate(fixed_gross_eur)
    assert compute_month_payroll(1, fixed_gross_eur, 0, 14, 7, (), rate)["net_eur"] == (
        pytest.approx(1882, abs=0.05)
    )
    # A bonus raises the withholding, so more gross is needed for the same net
    assert estimate_fixed_gross_from_net(1882, 14, 3000) > fixed_gross_eur
