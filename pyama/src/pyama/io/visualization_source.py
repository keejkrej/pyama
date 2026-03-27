"""Helpers for loading visualization sources from raw.zarr dataset references."""

from pathlib import Path

import numpy as np

from pyama.io.zarr import open_raw_zarr

_DATASET_REF_SEP = "::"


def parse_visualization_source(source_ref: str | Path) -> tuple[Path, str]:
    """Return the raw.zarr store path and dataset path for a dataset reference."""
    source_text = str(source_ref)
    if _DATASET_REF_SEP not in source_text:
        raise ValueError(
            f"Visualization source must be a raw.zarr dataset reference: {source_ref}"
        )

    store_text, dataset_path = source_text.split(_DATASET_REF_SEP, 1)
    normalized_dataset_path = dataset_path.replace("\\", "/").strip("/")
    if not store_text or not normalized_dataset_path:
        raise ValueError(f"Invalid visualization source reference: {source_ref}")
    return Path(store_text), normalized_dataset_path


def resolve_visualization_source_path(source_ref: str | Path) -> Path:
    """Return the backing filesystem path for a visualization source."""
    store_path, _ = parse_visualization_source(source_ref)
    return store_path


def visualization_source_exists(source_ref: str | Path) -> bool:
    """Return whether the visualization source exists."""
    store_path, dataset_path = parse_visualization_source(source_ref)
    if not store_path.exists():
        return False
    return open_raw_zarr(store_path, mode="r").dataset_exists(dataset_path)


def load_visualization_source(source_ref: str | Path) -> np.ndarray:
    """Load visualization source data from a raw.zarr dataset reference."""
    store_path, dataset_path = parse_visualization_source(source_ref)
    store = open_raw_zarr(store_path, mode="r")
    return np.asarray(store.get_required_array(dataset_path)[:])


__all__ = [
    "load_visualization_source",
    "parse_visualization_source",
    "resolve_visualization_source_path",
    "visualization_source_exists",
]
