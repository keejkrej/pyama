"""Visualization-related data structures."""

from dataclasses import dataclass, field

import numpy as np

from pyama_gui.types.common import ListRowState, OverlaySpec, PageState, PlotSpec


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class PositionData:
    """Data structure for cell position information."""

    frames: np.ndarray
    position: dict[str, np.ndarray]  # {"x": array, "y": array}


@dataclass
class FeatureData:
    """Data structure for cell feature frame series."""

    frame_points: np.ndarray
    features: dict[
        str, np.ndarray
    ]  # {"feature_name1": array, "feature_name2": array, ...}


@dataclass(frozen=True, slots=True)
class VisualizationViewState:
    """Render state for the visualization tab."""

    details_text: str = ""
    available_channels: list[str] = field(default_factory=list)
    selected_channels: list[str] = field(default_factory=list)
    min_position: int = 0
    max_position: int = 0
    selected_position: int = 0
    loading_project: bool = False
    loading_visualization: bool = False
    data_types: list[str] = field(default_factory=list)
    selected_data_type: str = ""
    current_image: np.ndarray | None = None
    frame_label: str = "Frame 0/0"
    trace_feature_options: list[str] = field(default_factory=list)
    selected_feature: str = ""
    trace_rows: list[ListRowState] = field(default_factory=list)
    trace_page: PageState = field(default_factory=PageState)
    trace_plot: PlotSpec | None = None
    overlays: list[OverlaySpec] = field(default_factory=list)
    can_visualize: bool = False
    can_save: bool = False
