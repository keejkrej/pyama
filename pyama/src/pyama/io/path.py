"""Trace CSV path resolution utilities.

This module provides centralized logic for resolving trace CSV file paths,
including support for inspected file versions. All code that needs to load
trace CSV files should use these utilities to ensure consistent behavior.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_trace_path(original_path: Path | None) -> Path | None:
    """Resolve trace CSV path, preferring the inspected trace when present."""
    if original_path is None:
        return None

    inspected_dir_path = original_path.parent / "inspected" / original_path.name
    if inspected_dir_path.exists():
        logger.debug("Using inspected traces file: %s", inspected_dir_path)
        return inspected_dir_path

    inspected_path = original_path.with_name(
        f"{original_path.stem}_inspected{original_path.suffix}"
    )

    if inspected_path.exists():
        logger.debug("Using inspected traces file: %s", inspected_path)
        return inspected_path

    return original_path


def get_trace_path_from_processing_results(proc_results, position_id: int) -> Path | None:
    """Get trace path from processing results with inspected resolution."""
    original_path = proc_results.get("position_data", {}).get(position_id, {}).get("traces")
    if original_path is None:
        return None

    return resolve_trace_path(original_path)


def get_trace_path_from_dict(position_data: dict) -> Path | None:
    """Get trace path from dict with inspected resolution.

    Convenience function that extracts the trace path from a dictionary
    (typically from position_data) and resolves it using resolve_trace_path().
    This is useful when working with dict-based data structures.

    Args:
        position_data: Dictionary containing position data

    Returns:
        Resolved trace path (inspected if available), or None if not found

    Examples:
        >>> position_data = {"traces": Path("/data/traces.csv"), ...}
        >>> trace_path = get_trace_path_from_dict(position_data)
    """
    traces_value = position_data.get("traces")
    if traces_value is None:
        return None

    original_path = Path(traces_value)
    return resolve_trace_path(original_path)
