"""Metric implementations for normalized statistics traces."""

import logging

import numpy as np
import pandas as pd

from pyama_core.types.statistics import SamplePair

logger = logging.getLogger(__name__)


def _source_area_filename(pair: SamplePair) -> str:
    """Return the area filename when available."""
    return pair.area_csv.name if pair.area_csv is not None else ""


def evaluate_onset_trace(
    time_values: np.ndarray, onset_time: float, slope: float, offset: float
) -> np.ndarray:
    """Evaluate the shifted-ReLU onset model."""
    return offset + slope * np.maximum(time_values - onset_time, 0.0)


def compute_auc_results(df: pd.DataFrame, pair: SamplePair) -> pd.DataFrame:
    """Compute per-cell AUC over the full normalized trace."""
    from scipy.integrate import trapezoid

    rows = []
    for fov, cell in df.index.unique().tolist():
        cell_df = df.loc[(fov, cell)].sort_values("time")
        time_values = cell_df["time"].to_numpy(dtype=np.float64)
        trace_values = cell_df["value"].to_numpy(dtype=np.float64)
        valid_mask = np.isfinite(time_values) & np.isfinite(trace_values)
        time_valid = time_values[valid_mask]
        trace_valid = trace_values[valid_mask]

        row = {
            "sample": pair.sample_name,
            "fov": int(fov),
            "cell": int(cell),
            "analysis_mode": "auc",
            "success": False,
            "n_points": int(len(trace_valid)),
            "time_start": np.nan,
            "time_end": np.nan,
            "auc": np.nan,
            "source_intensity_file": pair.intensity_csv.name,
            "source_area_file": _source_area_filename(pair),
        }
        if len(time_valid) >= 2:
            row["success"] = True
            row["time_start"] = float(time_valid[0])
            row["time_end"] = float(time_valid[-1])
            row["auc"] = float(trapezoid(trace_valid, time_valid))
        rows.append(row)

    return pd.DataFrame(rows)


def compute_onset_shifted_relu_results(
    df: pd.DataFrame, pair: SamplePair, fit_window_hours: float = 4.0
) -> pd.DataFrame:
    """Compute per-cell onset metrics from a shifted-ReLU fit."""
    from scipy.optimize import least_squares

    rows = []
    for fov, cell in df.index.unique().tolist():
        cell_df = df.loc[(fov, cell)].sort_values("time")
        time_values = cell_df["time"].to_numpy(dtype=np.float64)
        trace_values = cell_df["value"].to_numpy(dtype=np.float64)
        valid_mask = np.isfinite(time_values) & np.isfinite(trace_values)
        valid_mask &= time_values <= fit_window_hours
        time_valid = time_values[valid_mask]
        trace_valid = trace_values[valid_mask]

        row = {
            "sample": pair.sample_name,
            "fov": int(fov),
            "cell": int(cell),
            "analysis_mode": "onset_shifted_relu",
            "success": False,
            "n_points": int(len(trace_valid)),
            "fit_window_hours": float(fit_window_hours),
            "onset_time": np.nan,
            "slope": np.nan,
            "offset": np.nan,
            "r_squared": np.nan,
            "source_intensity_file": pair.intensity_csv.name,
            "source_area_file": _source_area_filename(pair),
        }

        if len(time_valid) < 4:
            rows.append(row)
            continue

        time_span = max(float(time_valid[-1] - time_valid[0]), 1e-9)
        onset_lower_bound = float(time_valid[0] - fit_window_hours)
        slope_guess = max(float(trace_valid[-1] - trace_valid[0]) / time_span, 0.0)
        offset_guess = float(np.nanmin(trace_valid))
        initial_guess = np.array(
            [
                min(
                    fit_window_hours / 2.0,
                    max(onset_lower_bound, float(np.median(time_valid))),
                ),
                slope_guess,
                offset_guess,
            ],
            dtype=np.float64,
        )
        bounds = (
            np.array([onset_lower_bound, 0.0, -np.inf], dtype=np.float64),
            np.array([fit_window_hours, np.inf, np.inf], dtype=np.float64),
        )

        try:
            result = least_squares(
                lambda params: (
                    trace_valid
                    - evaluate_onset_trace(time_valid, params[0], params[1], params[2])
                ),
                initial_guess,
                bounds=bounds,
            )
            fitted_trace = evaluate_onset_trace(
                time_valid, float(result.x[0]), float(result.x[1]), float(result.x[2])
            )
            ss_res = float(np.sum((trace_valid - fitted_trace) ** 2))
            ss_tot = float(np.sum((trace_valid - np.mean(trace_valid)) ** 2))
            r_squared = (
                0.0 if ss_tot <= 0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))
            )

            row["success"] = bool(result.success)
            row["onset_time"] = float(result.x[0])
            row["slope"] = float(result.x[1])
            row["offset"] = float(result.x[2])
            row["r_squared"] = r_squared
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Onset fitting failed for sample=%s fov=%s cell=%s: %s",
                pair.sample_name,
                fov,
                cell,
                exc,
            )

        rows.append(row)

    return pd.DataFrame(rows)
