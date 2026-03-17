"""Normalization helpers for folder-level statistics workflows."""

import logging

import numpy as np
import pandas as pd

from pyama.io.csv.analysis import load_analysis_csv
from pyama.types.statistics import SamplePair

logger = logging.getLogger(__name__)


def load_normalized_sample(
    pair: SamplePair,
    area_filter_size: int = 10,
    *,
    normalize_by_area: bool = True,
) -> pd.DataFrame:
    """Load one sample pair and return statistics traces by cell."""
    from scipy.ndimage import median_filter

    if normalize_by_area and area_filter_size < 1:
        raise ValueError("area_filter_size must be >= 1")

    intensity_df = (
        load_analysis_csv(pair.intensity_csv)
        .reset_index()
        .sort_values(["fov", "cell", "time"])
        .reset_index(drop=True)
    )

    if not normalize_by_area:
        trace_df = intensity_df[["fov", "cell", "time", "value"]].copy()
        logger.info(
            "Loaded raw intensity sample '%s' from %s (%d rows)",
            pair.sample_name,
            pair.intensity_csv.name,
            len(trace_df),
        )
        return trace_df.set_index(["fov", "cell"]).sort_index()

    if pair.area_csv is None:
        raise ValueError(
            f"Sample '{pair.sample_name}' cannot be area-normalized because no area CSV was found"
        )

    area_df = (
        load_analysis_csv(pair.area_csv)
        .reset_index()
        .sort_values(["fov", "cell", "time"])
        .reset_index(drop=True)
    )

    intensity_keys = intensity_df[["fov", "cell", "time"]]
    area_keys = area_df[["fov", "cell", "time"]]
    if len(intensity_df) != len(area_df) or not intensity_keys.equals(area_keys):
        raise ValueError(
            f"Sample '{pair.sample_name}' intensity/area rows are not aligned"
        )

    filtered_area = np.full(len(area_df), np.nan, dtype=np.float64)
    for _, group_df in area_df.groupby(["fov", "cell"], sort=False):
        values = group_df["value"].to_numpy(dtype=np.float64)
        filtered = median_filter(values, size=area_filter_size, mode="nearest")
        filtered_area[group_df.index.to_numpy()] = filtered

    intensity_values = intensity_df["value"].to_numpy(dtype=np.float64)
    normalized_values = np.full(len(intensity_df), np.nan, dtype=np.float64)
    valid_area_mask = np.isfinite(filtered_area) & (filtered_area > 0)
    valid_value_mask = valid_area_mask & np.isfinite(intensity_values)
    normalized_values[valid_value_mask] = (
        intensity_values[valid_value_mask] / filtered_area[valid_value_mask]
    )

    normalized_df = intensity_df[["fov", "cell", "time"]].copy()
    normalized_df["value"] = normalized_values

    logger.info(
        "Normalized sample '%s' from %s and %s (%d rows)",
        pair.sample_name,
        pair.intensity_csv.name,
        pair.area_csv.name,
        len(normalized_df),
    )

    return normalized_df.set_index(["fov", "cell"]).sort_index()
