"""Discovery utilities for merge_output statistics inputs."""

import logging
from pathlib import Path

from pyama_core.types.statistics import SamplePair

logger = logging.getLogger(__name__)

INTENSITY_SUFFIX = "_intensity_ch_1.csv"
AREA_SUFFIX = "_area_ch_0.csv"


def discover_sample_pairs(folder_path: Path | str) -> list[SamplePair]:
    """Discover intensity samples with optional area CSVs in a merge_output folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Statistics folder not found: {folder}")
    if not folder.is_dir():
        raise ValueError(f"Statistics folder must be a directory: {folder}")

    intensity_by_sample: dict[str, Path] = {}
    area_by_sample: dict[str, Path] = {}

    for csv_path in sorted(folder.glob("*.csv")):
        name = csv_path.name
        if name.endswith(INTENSITY_SUFFIX):
            sample_name = name[: -len(INTENSITY_SUFFIX)]
            intensity_by_sample[sample_name] = csv_path
            continue
        if name.endswith(AREA_SUFFIX):
            sample_name = name[: -len(AREA_SUFFIX)]
            area_by_sample[sample_name] = csv_path

    pairs: list[SamplePair] = []
    for sample_name in sorted(set(intensity_by_sample) | set(area_by_sample)):
        intensity_csv = intensity_by_sample.get(sample_name)
        area_csv = area_by_sample.get(sample_name)
        if intensity_csv is None:
            logger.warning(
                "Skipping sample '%s': missing %s file",
                sample_name,
                "intensity",
            )
            continue
        if area_csv is None:
            logger.warning(
                "Sample '%s' has no area CSV; area normalization will be unavailable",
                sample_name,
            )
        pairs.append(
            SamplePair(
                sample_name=sample_name,
                intensity_csv=intensity_csv,
                area_csv=area_csv,
            )
        )

    return pairs
