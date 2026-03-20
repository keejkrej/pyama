"""Shared progress payload helpers for pyama core."""

from collections.abc import Callable
from typing import Any, cast

from pyama.types.progress_payload import ProgressPayload


def _compute_progress_percent(current: int | None, total: int | None) -> int | None:
    if current is None or total is None or total <= 0:
        return None
    return int((current / total) * 100)


def build_progress_payload(
    *,
    step: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
    current_key: str = "current",
    total_key: str = "total",
    include_progress: bool = True,
    **extra: Any,
) -> ProgressPayload:
    """Build a standard progress payload with optional progress computation."""
    payload: ProgressPayload = {
        "step": step,
        "message": message,
    }
    payload_dict = cast(dict[str, object], payload)
    if current is not None:
        payload_dict[current_key] = current
    if total is not None:
        payload_dict[total_key] = total
    if include_progress:
        payload["progress"] = _compute_progress_percent(current, total)
    payload_dict.update(extra)
    return payload


def emit_progress(
    reporter: Callable[[ProgressPayload], None] | None,
    *,
    step: str,
    message: str,
    current: int | None = None,
    total: int | None = None,
    current_key: str = "current",
    total_key: str = "total",
    include_progress: bool = True,
    **extra: Any,
) -> ProgressPayload:
    """Build and emit a progress payload when a reporter is available."""
    payload = build_progress_payload(
        step=step,
        message=message,
        current=current,
        total=total,
        current_key=current_key,
        total_key=total_key,
        include_progress=include_progress,
        **extra,
    )
    if reporter is not None:
        reporter(payload)
    return payload


__all__ = [
    "build_progress_payload",
    "emit_progress",
]
