from pathlib import Path

import pyama.types as public_types

from pyama.io.config import load_config, save_config
from pyama.types.processing import Channels, ProcessingConfig, ProcessingParams


def test_processing_params_defaults_are_canonical() -> None:
    params = ProcessingParams()

    assert params.positions == "all"
    assert params.n_workers == 1
    assert params.background_weight == 1.0
    assert params.background_min_samples == 64
    assert params.to_dict() == {
        "positions": "all",
        "n_workers": 1,
        "background_weight": 1.0,
        "background_min_samples": 64,
    }


def test_processing_params_from_dict_ignores_legacy_keys() -> None:
    params = ProcessingParams.from_dict(
        {
            "positions": "0:3",
            "n_workers": 2,
            "background_weight": 0.5,
            "background_min_samples": 32,
            "copy_only": True,
            "segmentation_method": "cellpose",
            "tracking_method": "btrack",
        }
    )

    assert params == ProcessingParams(
        positions="0:3",
        n_workers=2,
        background_weight=0.5,
        background_min_samples=32,
    )


def test_processing_config_round_trip_normalizes_legacy_method_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "processing_config.yaml"
    config_path.write_text(
        "channels:\n"
        "  pc:\n"
        "    0: [area]\n"
        "  fl: {}\n"
        "params:\n"
        "  positions: 0:2\n"
        "  n_workers: 2\n"
        "  segmentation_method: cellpose\n"
        "  tracking_method: btrack\n",
        encoding="utf-8",
    )

    loaded = load_config(config_path)

    assert loaded == ProcessingConfig(
        channels=Channels(pc={0: ["area"]}, fl={}),
        params=ProcessingParams(positions="0:2", n_workers=2),
    )

    save_config(loaded, config_path)
    normalized = config_path.read_text(encoding="utf-8")

    assert "segmentation_method" not in normalized
    assert "tracking_method" not in normalized


def test_processing_config_to_dict_omits_legacy_method_keys() -> None:
    config = ProcessingConfig(
        channels=Channels(pc={0: ["area"]}, fl={}),
        params=ProcessingParams.from_dict(
            {
                "positions": "1:4",
                "segmentation_method": "cellpose",
                "tracking_method": "btrack",
            }
        ),
    )

    assert config.to_dict() == {
        "channels": {"pc": {0: ["area"]}, "fl": {}},
        "params": {
            "positions": "1:4",
            "n_workers": 1,
            "background_weight": 1.0,
            "background_min_samples": 64,
        },
    }


def test_public_types_no_longer_export_method_enums() -> None:
    assert not hasattr(public_types, "SegmentationMethod")
    assert not hasattr(public_types, "TrackingMethod")
