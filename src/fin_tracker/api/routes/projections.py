"""Projection endpoints: defaults from my data and scenario simulation."""

from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends

from fin_tracker.api.dependencies import get_store
from fin_tracker.api.models import (
    ScenarioParametersModel,
    ScenarioResult,
    SimulationRequest,
)
from fin_tracker.api.serialization import dataframe_to_records
from fin_tracker.api.store import FinanceDataStore
from fin_tracker.projections import (
    SalaryStep,
    ScenarioParameters,
    estimate_baseline,
    simulate_percentiles,
    simulate_scenario,
    summarize_projection,
)

router = APIRouter(prefix="/api/projections", tags=["projections"])
Store = Annotated[FinanceDataStore, Depends(get_store)]


def to_scenario_parameters(model: ScenarioParametersModel) -> ScenarioParameters:
    """Convert the API model to the simulation's parameters."""
    dict_parameters = model.model_dump()
    dict_parameters["salary_schedule"] = tuple(
        SalaryStep(**step) for step in dict_parameters["salary_schedule"]
    )
    return ScenarioParameters(**dict_parameters)


def get_start_month(start_month: str | None) -> pd.Period:
    """First projected month: the requested one, or next month."""
    if start_month:
        return pd.Period(start_month, freq="M")
    return pd.Timestamp.today().to_period("M") + 1


@router.get("/baseline", response_model=ScenarioParametersModel)
def get_baseline(store: Store) -> dict:
    """Scenario defaults estimated from the last complete months of my data."""
    return estimate_baseline(
        store.df_transactions, store.dict_net_worth, store.end_date
    )


@router.post("/simulate", response_model=list[ScenarioResult])
def simulate(request: SimulationRequest) -> list[dict]:
    """Project every scenario; percentiles only when ``simulations`` > 0."""
    start_month = get_start_month(request.start_month)
    list_results = []
    for scenario in request.scenarios:
        parameters = to_scenario_parameters(scenario.parameters)
        df_projection, df_payroll_years = simulate_scenario(parameters, start_month)
        df_percentiles = (
            simulate_percentiles(parameters, start_month, request.simulations)
            if request.simulations > 0
            else pd.DataFrame()
        )
        list_results.append(
            {
                "name": scenario.name,
                "summary": summarize_projection(parameters, df_projection),
                "payroll_years": dataframe_to_records(df_payroll_years),
                "points": dataframe_to_records(df_projection),
                "percentiles": dataframe_to_records(df_percentiles),
            }
        )
    return list_results
