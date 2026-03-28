"""Sample YAML and statistics sample discovery helpers."""

import logging
from pathlib import Path
from typing import cast

import yaml

from pyama.types.processing import MergeSamplePayload, SamplesFilePayload
from pyama.types.statistics import SamplePair

logger = logging.getLogger(__name__)

INTENSITY_DIR = "intensity_total_c1"
AREA_DIR = "area_c0"


def read_samples_yaml(path: Path) -> SamplesFilePayload:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Samples YAML must contain a mapping at top level")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Samples YAML must contain a 'samples' list")

    validated_samples: list[MergeSamplePayload] = []
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample {index} must be a mapping")
        sample_dict = cast(dict[object, object], sample)
        name = sample_dict.get("name")
        positions = sample_dict.get("positions")
        if not isinstance(name, str):
            raise ValueError(f"Sample {index} is missing a name")
        if isinstance(positions, str):
            validated_samples.append({"name": name, "positions": positions})
            continue
        if not isinstance(positions, list):
            raise ValueError(f"Sample {index} must include a string or list of positions")
        validated_positions: list[int | str] = []
        for position in positions:
            if isinstance(position, bool) or not isinstance(position, int | str):
                raise ValueError(
                    f"Sample {index} list positions must contain only integers or strings"
                )
            validated_positions.append(position)
        validated_samples.append({"name": name, "positions": validated_positions})
    return {"samples": validated_samples}


def discover_statistics_sample_pairs(folder_path: Path | str) -> list[SamplePair]:
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


__all__ = ["discover_statistics_sample_pairs", "read_samples_yaml"]
