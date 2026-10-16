"""Projections of my net worth under editable scenarios."""

from fin_tracker.projections.baseline import estimate_baseline
from fin_tracker.projections.payroll import SalaryStep
from fin_tracker.projections.simulation import (
    ScenarioParameters,
    simulate_percentiles,
    simulate_scenario,
    summarize_projection,
)

__all__ = [
    "SalaryStep",
    "ScenarioParameters",
    "estimate_baseline",
    "simulate_percentiles",
    "simulate_scenario",
    "summarize_projection",
]
