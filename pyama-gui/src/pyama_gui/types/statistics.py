"""Statistics-related UI data structures."""

from dataclasses import dataclass, field

from pyama.types import StatisticsRequest
from pyama_gui.types.common import PageState, PlotSpec


@dataclass(frozen=True, slots=True)
class StatisticsViewState:
    """Render state for the statistics tab."""

    sample_names: list[str] = field(default_factory=list)
    normalization_available: bool = False
    normalize_by_area: bool = False
    frame_interval_minutes: float = 10.0
    fit_window_min: float = 240.0
    area_filter_size: int = 10
    running: bool = False
    selected_sample: str | None = None
    selected_metric: str | None = None
    metric_options: list[tuple[str, str]] = field(default_factory=list)
    detail_stats_text: str = ""
    detail_page: PageState = field(default_factory=PageState)
    visible_trace_ids: list[tuple[int, int]] = field(default_factory=list)
    trace_plot: PlotSpec | None = None
    comparison_plot: PlotSpec | None = None
    summary_rows: list[tuple[str, int, float, float, float, float]] = field(default_factory=list)


__all__ = ["StatisticsRequest", "StatisticsViewState"]
