"""Shared UI state data structures."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppState:
    """Shared application state exposed to the shell."""

    workspace_dir: Path | None
    status_message: str
    busy: bool


@dataclass(frozen=True, slots=True)
class PageState:
    """Pagination state for list-style UI sections."""

    label: str = "Page 1 of 1"
    can_previous: bool = False
    can_next: bool = False


@dataclass(frozen=True, slots=True)
class ListRowState:
    """Display state for list/table rows."""

    label: str
    value: object
    color: str | None = None
    selected: bool = False


@dataclass(frozen=True, slots=True)
class PlotSpec:
    """Plot-ready state for the shared Matplotlib canvas."""

    kind: str = "lines"
    lines_data: list[tuple[object, object]] = field(default_factory=list)
    styles_data: list[dict[str, object]] = field(default_factory=list)
    histogram_data: list[float] = field(default_factory=list)
    histogram_bins: int = 30
    boxplot_groups: dict[str, list[float]] = field(default_factory=dict)
    title: str = ""
    x_label: str = ""
    y_label: str = ""
    annotation_text: str = ""


@dataclass(frozen=True, slots=True)
class OverlaySpec:
    """Image overlay state for visualization canvases."""

    overlay_id: str
    properties: dict[str, object]


__all__ = [
    "AppState",
    "ListRowState",
    "OverlaySpec",
    "PageState",
    "PlotSpec",
]
