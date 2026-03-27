"""Modeling-related data structures."""

from dataclasses import dataclass, field
from typing import Literal

from pyama_gui.types.common import ListRowState, PageState, PlotSpec


@dataclass(frozen=True, slots=True)
class ParameterOptionState:
    """Selectable preset option for a model parameter."""

    key: str
    label: str
    value: float


@dataclass(frozen=True, slots=True)
class ParameterEditorState:
    """Row state for the modeling parameter editor."""

    key: str
    name: str
    mode: Literal["fit", "fixed"]
    is_interest: bool
    value: float
    min_value: float | None = None
    max_value: float | None = None
    preset_options: tuple[ParameterOptionState, ...] = ()
    selected_preset: str | None = None


@dataclass(slots=True)
class FittingRequest:
    """Parameters for triggering a fitting job."""

    model_type: str
    frame_interval_minutes: float = 10.0
    model_params: dict[str, float] = field(default_factory=dict)
    model_bounds: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelingViewState:
    """Render state for the modeling tab."""

    model_names: list[str] = field(default_factory=list)
    model_type: str = ""
    frame_interval_minutes: float = 10.0
    parameters: tuple[ParameterEditorState, ...] = ()
    running: bool = False
    raw_plot: PlotSpec | None = None
    quality_plot: PlotSpec | None = None
    histogram_plot: PlotSpec | None = None
    scatter_plot: PlotSpec | None = None
    quality_rows: list[ListRowState] = field(default_factory=list)
    quality_stats_label: str = "Good: 0%, Mid: 0%, Bad: 0%"
    quality_page: PageState = field(default_factory=PageState)
    parameter_options: list[tuple[str, str]] = field(default_factory=list)
    selected_parameter: str | None = None
    x_parameter: str | None = None
    y_parameter: str | None = None
    filter_good_only: bool = False
