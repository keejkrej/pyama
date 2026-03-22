"""Function-based service entrypoints for modeling."""

import logging
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from pyama.apps.modeling.fitting import (
    analyze_fitting_quality,
    fit_model,
    fit_trace_data,
)
from pyama.apps.modeling.models import MODELS, get_model, get_types, list_models
from pyama.io.csv import load_analysis_csv
from pyama.types.modeling import FittingResult, ModelParameter
from pyama.types.tasks import ProgressPayload
from pyama.utils.progress import emit_progress

logger = logging.getLogger(__name__)


def _build_parameter_sets(
    model,
    model_params: dict[str, float] | None,
    model_bounds: dict[str, tuple[float, float]] | None,
) -> tuple[dict[str, ModelParameter], dict[str, ModelParameter]]:
    fixed_params: dict[str, ModelParameter] = {}
    fit_params: dict[str, ModelParameter] = {}
    for param_name, param in model.get_parameters().items():
        value = (
            model_params.get(param_name, param.value) if model_params else param.value
        )
        resolved_param = param.clone(value=value)
        if resolved_param.mode == "fixed":
            fixed_params[param_name] = resolved_param
            continue
        if model_bounds and param_name in model_bounds:
            lb, ub = model_bounds[param_name]
        else:
            lb = resolved_param.lb
            ub = resolved_param.ub
        fit_params[param_name] = resolved_param.clone(lb=lb, ub=ub)
    return fixed_params, fit_params


def _flatten_results(
    model_type: str,
    results: list[tuple[tuple[int, int], FittingResult]],
) -> pd.DataFrame | None:
    if not results:
        return None

    flattened_results = []
    for (position, roi), result in results:
        row = {
            "position": position,
            "roi": roi,
            "model_type": model_type,
            "success": result.success,
            "r_squared": result.r_squared,
        }
        row.update(
            {
                param_name: param.value
                for param_name, param in result.fixed_params.items()
            }
        )
        row.update(
            {
                param_name: param.value
                for param_name, param in result.fitted_params.items()
            }
        )
        flattened_results.append(row)

    if not flattened_results:
        return None
    return pd.DataFrame(flattened_results)


def fit_csv_file(
    csv_file: Path,
    model_type: str,
    model_params: dict[str, float] | None = None,
    model_bounds: dict[str, tuple[float, float]] | None = None,
    *,
    frame_interval_minutes: float = 10.0,
    progress_reporter: Callable[[ProgressPayload], None] | None = None,
) -> tuple[pd.DataFrame | None, Path | None]:
    """Fit traces in one analysis CSV file and persist the results."""
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_file}")

    logger.info(
        "Processing %s with model=%s (manual_params=%d, manual_bounds=%d)",
        csv_file.name,
        model_type,
        len(model_params or {}),
        len(model_bounds or {}),
    )

    df = load_analysis_csv(
        csv_file,
        frame_interval_minutes=frame_interval_minutes,
    )
    model = get_model(model_type)
    fixed_params, fit_params = _build_parameter_sets(model, model_params, model_bounds)

    def progress_callback(current: int, total: int, message: str) -> None:
        current_idx = current + 1
        emit_progress(
            progress_reporter,
            step="analysis_fitting",
            file=csv_file.name,
            current=current_idx,
            total=total if total > 0 else None,
            message=message,
        )

    results = fit_trace_data(
        df,
        model_type,
        fixed_params=fixed_params,
        fit_params=fit_params,
        progress_callback=progress_callback,
    )

    results_df = _flatten_results(model_type, results)
    if results_df is None or results_df.empty:
        return results_df, None

    saved_csv_path = csv_file.with_name(f"{csv_file.stem}_fitted_{model_type}.csv")
    try:
        results_df.to_csv(saved_csv_path, index=False)
        logger.info(
            "Saved fitted results to %s (%d rows)", saved_csv_path, len(results_df)
        )
    except Exception as exc:  # pragma: no cover - best effort I/O
        logger.warning("Failed to save fitted results for %s: %s", saved_csv_path, exc)
        saved_csv_path = None

    return results_df, saved_csv_path


__all__ = [
    "MODELS",
    "analyze_fitting_quality",
    "fit_csv_file",
    "fit_model",
    "fit_trace_data",
    "get_model",
    "get_types",
    "list_models",
]
