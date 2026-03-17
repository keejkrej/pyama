"""Statistics-related data structures."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class SamplePair:
    """Intensity input and optional area input for one sample."""

    sample_name: str
    intensity_csv: Path
    area_csv: Path | None


@dataclass(slots=True)
class StatisticsRequest:
    """Parameters for running a statistics job across a merge_output folder."""

    mode: str
    folder_path: Path
    normalize_by_area: bool = False
    fit_window_hours: float = 4.0
    area_filter_size: int = 10
