"""Tests for fin_tracker.api.routes.projections."""

import pandas as pd
import pytest

from fin_tracker.api.models import ScenarioParametersModel
from fin_tracker.api.routes.projections import get_start_month, to_scenario_parameters
from fin_tracker.projections import SalaryStep


def test_get_start_month():
    assert get_start_month("2027-01") == pd.Period("2027-01", freq="M")
    assert get_start_month(None) == pd.Timestamp.today().to_period("M") + 1


def test_to_scenario_parameters_builds_salary_steps():
    parameters = to_scenario_parameters(
        ScenarioParametersModel(
            salary_schedule=[{"start_month": "2026-01", "gross_salary_eur": 30000}],
            retention_rate_override=0.15,
        )
    )
    assert parameters.salary_schedule == (SalaryStep("2026-01", 30000, 0.0),)
    assert parameters.retention_rate_override == 0.15


def test_get_baseline_from_synthetic_data(client):
    dict_baseline = client.get("/api/projections/baseline").json()
    assert dict_baseline["start_investments_eur"] == pytest.approx(72.0)
    assert dict_baseline["horizon_years"] == 10
    assert 0 < dict_baseline["investment_return"] < 0.1


def test_simulate_several_scenarios(client):
    dict_parameters = {
        "horizon_years": 2,
        "start_cash_eur": 1000,
        "salary_schedule": [
            {
                "start_month": "2027-01",
                "gross_salary_eur": 30000,
                "gross_bonus_eur": 2000,
            }
        ],
        "monthly_expenses_eur": 1500,
        "monthly_investment_eur": 300,
        "investment_return": 0.05,
        "investment_volatility": 0.1,
    }
    list_results = client.post(
        "/api/projections/simulate",
        json={
            "scenarios": [
                {"name": "Base", "parameters": dict_parameters},
                {
                    "name": "Sin invertir",
                    "parameters": {**dict_parameters, "monthly_investment_eur": 0},
                },
            ],
            "simulations": 100,
            "start_month": "2027-01",
        },
    ).json()

    assert [result["name"] for result in list_results] == ["Base", "Sin invertir"]
    assert len(list_results[0]["points"]) == 24
    assert list_results[0]["points"][0]["month"] == "2027-01"
    assert len(list_results[0]["percentiles"]) == 24
    assert list_results[1]["summary"]["final_investments_eur"] == 0
    assert [year["year"] for year in list_results[0]["payroll_years"]] == [2027, 2028]
    assert list_results[0]["payroll_years"][0]["gross_eur"] == pytest.approx(32000)


def test_simulate_without_monte_carlo_and_invalid_input(client):
    dict_body = {
        "scenarios": [{"name": "A", "parameters": {"horizon_years": 1}}],
        "simulations": 0,
    }
    assert (
        client.post("/api/projections/simulate", json=dict_body).json()[0][
            "percentiles"
        ]
        == []
    )

    dict_body["scenarios"][0]["parameters"]["horizon_years"] = 80
    assert client.post("/api/projections/simulate", json=dict_body).status_code == 422
    assert (
        client.post("/api/projections/simulate", json={"scenarios": []}).status_code
        == 422
    )
