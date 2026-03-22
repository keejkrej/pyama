"""Statistics-related data structures."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SamplePair:
    """Intensity input and optional area input for one sample."""

    sample_name: str
    intensity_csv: Path
    area_csv: Path | None


@dataclass(frozen=True, slots=True)
class StatisticsRequest:
    """Parameters for running a statistics job across a traces_merged folder."""

    mode: str
    folder_path: Path
    normalize_by_area: bool = False
    frame_interval_minutes: float = 10.0
    fit_window_min: float = 240.0
    area_filter_size: int = 10
