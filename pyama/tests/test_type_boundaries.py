from pathlib import Path

import pytest

from pyama.apps.processing.merge import normalize_samples
from pyama.io.samples import read_samples_yaml
from pyama.types.processing import MergeSample


def test_merge_yaml_parses_payload_then_normalizes_to_dataclasses(tmp_path: Path) -> None:
    sample_file = tmp_path / "samples.yaml"
    sample_file.write_text(
        "samples:\n"
        "  - name: sample_a\n"
        "    positions: 0:3\n"
        "  - name: sample_b\n"
        "    positions: [4, 5]\n",
        encoding="utf-8",
    )

    payload = read_samples_yaml(sample_file)
    samples = normalize_samples(payload["samples"])

    assert payload == {
        "samples": [
            {"name": "sample_a", "positions": "0:3"},
            {"name": "sample_b", "positions": [4, 5]},
        ]
    }
    assert samples == [
        MergeSample(name="sample_a", positions=(0, 1, 2)),
        MergeSample(name="sample_b", positions=(4, 5)),
    ]


def test_merge_yaml_rejects_legacy_fovs_key(tmp_path: Path) -> None:
    sample_file = tmp_path / "samples.yaml"
    sample_file.write_text(
        "samples:\n"
        "  - name: sample_a\n"
        "    fovs: 0-2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="positions"):
        read_samples_yaml(sample_file)


def test_merge_normalization_rejects_legacy_dash_ranges() -> None:
    with pytest.raises(ValueError):
        normalize_samples([{"name": "sample_a", "positions": "0-2"}])


def test_merge_normalization_accepts_canonical_positions_key() -> None:
    samples = normalize_samples(
        [
            {"name": "sample_a", "positions": "0:3"},
            {"name": "sample_b", "positions": [4, 5]},
        ]
    )

    assert samples == [
        MergeSample(name="sample_a", positions=(0, 1, 2)),
        MergeSample(name="sample_b", positions=(4, 5)),
    ]
