"""Discovery utilities for traces_merged statistics inputs."""

import logging
from pathlib import Path

from pyama.types.statistics import SamplePair

logger = logging.getLogger(__name__)

INTENSITY_DIR = "intensity_total_c1"
AREA_DIR = "area_c0"


def discover_sample_pairs(folder_path: Path | str) -> list[SamplePair]:
    """Discover intensity samples with optional area CSVs in a traces_merged folder."""
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Statistics folder not found: {folder}")
    if not folder.is_dir():
        raise ValueError(f"Statistics folder must be a directory: {folder}")

    intensity_by_sample: dict[str, Path] = {}
    area_by_sample: dict[str, Path] = {}

    intensity_dir = folder / INTENSITY_DIR
    area_dir = folder / AREA_DIR
    if intensity_dir.exists():
        for csv_path in sorted(intensity_dir.glob("*.csv")):
            intensity_by_sample[csv_path.stem] = csv_path
    if area_dir.exists():
        for csv_path in sorted(area_dir.glob("*.csv")):
            area_by_sample[csv_path.stem] = csv_path
    if not intensity_by_sample and not area_by_sample:
        for csv_path in sorted(folder.glob("*.csv")):
            name = csv_path.name
            if name.endswith("_intensity_ch_1.csv"):
                sample_name = name[: -len("_intensity_ch_1.csv")]
                intensity_by_sample[sample_name] = csv_path
            elif name.endswith("_area_ch_0.csv"):
                sample_name = name[: -len("_area_ch_0.csv")]
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
