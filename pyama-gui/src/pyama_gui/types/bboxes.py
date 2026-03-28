"""BBox alignment state models."""

from dataclasses import dataclass, field

import numpy as np

from pyama_gui.types.common import OverlaySpec


@dataclass(frozen=True, slots=True)
class BBoxesViewState:
    """Render state for the bbox alignment tab."""

    microscopy_path_label: str = ""
    workspace_path_label: str = ""
    position_options: list[tuple[str, int]] = field(default_factory=list)
    channel_options: list[tuple[str, int]] = field(default_factory=list)
    z_options: list[tuple[str, int]] = field(default_factory=list)
    selected_position: int | None = None
    selected_channel: int | None = None
    selected_z: int | None = None
    frame_max: int = 0
    selected_frame: int = 0
    time_values: list[str] = field(default_factory=list)
    time_value_label: str = "0"
    current_image: np.ndarray | None = None
    grid_values: dict[str, object] = field(default_factory=dict)
    overlays: list[OverlaySpec] = field(default_factory=list)
    included_count: int = 0
    excluded_count: int = 0
    contrast_domain_min: int = 0
    contrast_domain_max: int = 65535
    contrast_min: int = 0
    contrast_max: int = 65535
    loading_metadata: bool = False
    loading_frame: bool = False
    can_save: bool = False
    can_disable_edge: bool = False
    save_path_label: str = ""


__all__ = ["BBoxesViewState"]
