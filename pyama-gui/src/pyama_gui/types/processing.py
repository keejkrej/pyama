"""Processing-related data structures."""

from dataclasses import dataclass, field

from pyama_gui.types.common import ListRowState

@dataclass(frozen=True, slots=True)
class ProcessingViewState:
    """Render state for the processing tab."""

    microscopy_path_label: str = ""
    phase_channel_options: list[tuple[str, int]] = field(default_factory=list)
    fluorescence_channel_options: list[tuple[str, int]] = field(default_factory=list)
    available_pc_features: list[str] = field(default_factory=list)
    available_fl_features: list[str] = field(default_factory=list)
    selected_phase_channel: int | None = None
    fluorescence_feature_rows: list[tuple[str, int, str]] = field(default_factory=list)
    parameter_values: dict[str, dict[str, object]] = field(default_factory=dict)
    workflow_running: bool = False
    workflow_progress: int = 0
    workflow_message: str = ""
    samples: list[dict[str, str]] = field(default_factory=list)
    sample_rows: list[ListRowState] = field(default_factory=list)
    merge_running: bool = False


__all__ = [
    "ProcessingViewState",
]
