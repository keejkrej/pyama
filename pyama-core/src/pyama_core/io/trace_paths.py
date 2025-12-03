"""Trace CSV path resolution utilities.

This module provides centralized logic for resolving trace CSV file paths,
including support for inspected file versions. All code that needs to load
trace CSV files should use these utilities to ensure consistent behavior.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_trace_path(original_path: Path | None) -> Path | None:
    """Resolve trace CSV path, preferring inspected version if available.

    This is the single source of truth for inspected file logic. It checks
    if an inspected version of the trace CSV exists (with "_inspected" suffix
    before the file extension) and returns that if available, otherwise
    returns the original path.

    Args:
        original_path: Original trace CSV path

    Returns:
        Inspected path if exists, otherwise original path, or None if input is None

    Examples:
        >>> from pathlib import Path
        >>> original = Path("/data/traces.csv")
        >>> resolved = resolve_trace_path(original)
        >>> # If /data/traces_inspected.csv exists, returns that
        >>> # Otherwise returns /data/traces.csv
    """
    if original_path is None:
        return None

    # Check for inspected version
    inspected_path = original_path.with_name(
        f"{original_path.stem}_inspected{original_path.suffix}"
    )

    if inspected_path.exists():
        logger.debug("Using inspected traces file: %s", inspected_path)
        return inspected_path

    return original_path


def get_trace_path_from_dict(fov_data: dict) -> Path | None:
    """Get trace path from dict with inspected resolution.

    Convenience function that extracts the trace path from a dictionary
    (typically from fov_data) and resolves it using resolve_trace_path().
    This is useful when working with dict-based data structures.

    Args:
        fov_data: Dictionary containing FOV data (e.g., from project_data["fov_data"][fov_id])

    Returns:
        Resolved trace path (inspected if available), or None if not found

    Examples:
        >>> fov_data = {"traces": Path("/data/traces.csv"), ...}
        >>> trace_path = get_trace_path_from_dict(fov_data)
    """
    traces_value = fov_data.get("traces")
    if traces_value is None:
        return None

    original_path = Path(traces_value)
    return resolve_trace_path(original_path)
