"""Typed progress payloads used across pyama core services."""

from typing import Literal, TypedDict


class ProgressPayload(TypedDict, total=False):
    """Progress payload emitted by core services and consumed by the task layer."""

    step: str
    message: str
    progress: int | None
    current: int | None
    total: int | None
    event: Literal["frame"]
    fov: int
    channel: int
    t: int
    T: int
    worker_id: int
    file: str
    mode: str
    sample: str
    source_path: str
    cached_path: str
    step_current: int
    step_total: int
    overall_current: int
    overall_total: int
    overall_percent: int | None


class FrameProgressPayload(ProgressPayload, total=False):
    """Frame-level workflow progress payload."""

    event: Literal["frame"]
    fov: int
    channel: int
    t: int
    T: int
    worker_id: int


__all__ = ["FrameProgressPayload", "ProgressPayload"]
