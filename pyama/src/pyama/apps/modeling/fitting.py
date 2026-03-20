"""
Simplified fitting utilities for trace data analysis.
"""

from typing import Callable

import numpy as np
import pandas as pd

from pyama.apps.modeling.models import get_model
from pyama.types.modeling import FittingResult, ModelParameter


def analyze_fitting_quality(results_df: pd.DataFrame) -> dict:
    """
    Analyze fitting quality metrics from results DataFrame.

    Args:
        results_df: DataFrame containing fitting results with 'r_squared' column

    Returns:
        Dictionary containing quality metrics
    """
    if results_df is None or "r_squared" not in results_df.columns:
        return {}

    r_squared = pd.to_numeric(results_df["r_squared"], errors="coerce").dropna()
    if r_squared.empty:
        return {}

    good_count = (r_squared > 0.9).sum()
    fair_count = ((r_squared > 0.7) & (r_squared <= 0.9)).sum()
    poor_count = (r_squared <= 0.7).sum()
    total = len(r_squared)

    quality_metrics = {
        "r_squared_values": r_squared.values,
        "cell_indices": list(range(len(r_squared))),
        "colors": [
            "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red" for r2 in r_squared
        ],
        "good_percentage": (good_count / total) * 100 if total > 0 else 0,
        "fair_percentage": (fair_count / total) * 100 if total > 0 else 0,
        "poor_percentage": (poor_count / total) * 100 if total > 0 else 0,
        "good_count": good_count,
        "fair_count": fair_count,
        "poor_count": poor_count,
        "total_count": total,
    }

    return quality_metrics


def fit_model(
    model,
    t_data: np.ndarray,
    y_data: np.ndarray,
    fixed_params: dict[str, ModelParameter],
    fit_params: dict[str, ModelParameter],
) -> FittingResult:
    """Fit a model to time series data.

    Args:
        model: Model module with eval function
        t_data: Time array
        y_data: Data array
        fixed_params: Fixed-parameter dict
        fit_params: Fit-parameter dict with initial values and bounds

    Returns:
        FittingResult with fixed_params, fitted_params, success status, and r_squared
    """
    # Unwrap parameters
    fit_param_names = list(fit_params.keys())
    p0 = np.array([fit_params[name].value for name in fit_param_names])
    lower_bounds = [fit_params[param_name].lb for param_name in fit_param_names]
    upper_bounds = [fit_params[param_name].ub for param_name in fit_param_names]

    # Clean data
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    t_clean = t_data[mask]
    y_clean = y_data[mask]
    n_valid_points = int(np.sum(mask))
    n_fit_params = len(fit_param_names)

    if n_valid_points < n_fit_params:
        return FittingResult(
            fixed_params=fixed_params,
            fitted_params=fit_params,
            success=False,
            r_squared=0.0,
        )

    # Create residual function
    def residual_func(params):
        fitted_params: dict[str, ModelParameter] = {
            param_name: ModelParameter(
                key=fit_params[param_name].key,
                name=fit_params[param_name].name,
                value=params[idx],
                mode=fit_params[param_name].mode,
                is_interest=fit_params[param_name].is_interest,
                lb=fit_params[param_name].lb,
                ub=fit_params[param_name].ub,
                presets=fit_params[param_name].presets,
            )
            for idx, param_name in enumerate(fit_param_names)
        }
        return y_clean - model.eval(t_clean, fixed_params, fitted_params)

    try:
        from scipy import optimize

        result = optimize.least_squares(
            residual_func,
            p0,
            bounds=(lower_bounds, upper_bounds),
            loss="soft_l1",
        )

        # Compute r-squared
        ss_res = float(np.sum(result.fun**2))
        ss_tot = float(np.sum((y_clean - np.mean(y_clean)) ** 2))
        r_squared = max(0.0, min(1.0, 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0))

        # Create fitted-parameter dict with optimized values
        fitted_params: dict[str, ModelParameter] = {
            param_name: ModelParameter(
                key=fit_params[param_name].key,
                name=fit_params[param_name].name,
                value=result.x[idx],
                mode=fit_params[param_name].mode,
                is_interest=fit_params[param_name].is_interest,
                lb=fit_params[param_name].lb,
                ub=fit_params[param_name].ub,
                presets=fit_params[param_name].presets,
            )
            for idx, param_name in enumerate(fit_param_names)
        }

        return FittingResult(
            fixed_params=fixed_params,
            fitted_params=fitted_params,
            success=result.success,
            r_squared=r_squared,
        )
    except Exception:
        # Return initial fit_params on error
        fitted_params: dict[str, ModelParameter] = {
            param_name: ModelParameter(
                key=fit_params[param_name].key,
                name=fit_params[param_name].name,
                value=p0[idx],
                mode=fit_params[param_name].mode,
                is_interest=fit_params[param_name].is_interest,
                lb=fit_params[param_name].lb,
                ub=fit_params[param_name].ub,
                presets=fit_params[param_name].presets,
            )
            for idx, param_name in enumerate(fit_param_names)
        }
        return FittingResult(
            fixed_params=fixed_params,
            fitted_params=fitted_params,
            success=False,
            r_squared=0.0,
        )


def fit_trace_data(
    df: pd.DataFrame,
    model_type: str,
    fixed_params: dict[str, ModelParameter] | None = None,
    fit_params: dict[str, ModelParameter] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[tuple[tuple[int, int], FittingResult]]:
    """Fit trace data for all cells in the DataFrame.

    Args:
        df: DataFrame with MultiIndex (position, roi) and 'time_min', 'value' columns
        model_type: Type of model to fit
        fixed_params: Optional fixed-parameter dict (shared across all cells)
        fit_params: Optional fit-parameter dict with initial values and bounds (shared across all cells)
        progress_callback: Optional callback function(current, total, message) for progress updates

    Returns:
        List of tuples ((position, roi), FittingResult) for all traces in the DataFrame
    """
    # Setup: get model and resolve defaults (done once, not in loop)
    try:
        model = get_model(model_type.lower())
    except ValueError:
        return []

    if fixed_params is None:
        fixed_params = model.get_fixed_parameters()
    if fit_params is None:
        fit_params = model.get_fit_parameters()

    trace_ids = df.index.unique().tolist()
    total_cells = len(trace_ids)

    results = []
    for cell_idx, (position, roi) in enumerate(trace_ids):
        cell_data = df.loc[(position, roi)].sort_values("frame")
        time_data = cell_data["time_min"].values.astype(np.float64)
        trace_data = cell_data["value"].values.astype(np.float64)

        result = fit_model(
            model,
            time_data,
            trace_data,
            fixed_params=fixed_params,
            fit_params=fit_params,
        )
        results.append(((position, roi), result))

        if progress_callback:
            progress_callback(cell_idx, total_cells, "Fitting cells")

    return results
