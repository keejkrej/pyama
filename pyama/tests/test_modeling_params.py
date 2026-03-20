from pathlib import Path

import pandas as pd

from pyama.apps.modeling.service import fit_csv_file
from pyama.apps.modeling.models import get_model
from pyama.apps.modeling.models.preset import (
    DEFAULT_PROTEIN_DEGRADATION_RATE_MIN,
    PROTEIN_PRESETS,
)


def test_base_model_exposes_expected_parameter_metadata() -> None:
    model = get_model("base")
    params = model.get_parameters()

    assert list(params) == [
        "protein_degradation_rate_min",
        "time_onset_min",
        "ktl_m0_min",
        "mrna_degradation_rate_min",
        "intensity_offset",
    ]
    assert params["protein_degradation_rate_min"].mode == "fixed"
    assert params["protein_degradation_rate_min"].is_interest is False
    assert [
        preset.key for preset in params["protein_degradation_rate_min"].presets
    ] == [
        "gfp",
        "dsred",
    ]
    assert params["time_onset_min"].is_interest is True
    assert params["mrna_degradation_rate_min"].is_interest is True
    assert params["ktl_m0_min"].is_interest is False
    assert params["intensity_offset"].is_interest is False


def test_protein_presets_share_current_default_value() -> None:
    assert PROTEIN_PRESETS["gfp"].value == DEFAULT_PROTEIN_DEGRADATION_RATE_MIN
    assert PROTEIN_PRESETS["dsred"].value == DEFAULT_PROTEIN_DEGRADATION_RATE_MIN


def test_fit_csv_file_serializes_renamed_parameter_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 0.5},
            {"frame": 6, "fov": 0, "cell": 0, "value": 1.0},
            {"frame": 12, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 18, "fov": 0, "cell": 0, "value": 1.5},
            {"frame": 24, "fov": 0, "cell": 0, "value": 1.0},
        ]
    ).to_csv(csv_path, index=False)

    results_df, _ = fit_csv_file(
        csv_path,
        "base",
        frame_interval_minutes=10.0,
    )

    assert results_df is not None
    for column in (
        "protein_degradation_rate_min",
        "time_onset_min",
        "ktl_m0_min",
        "mrna_degradation_rate_min",
        "intensity_offset",
    ):
        assert column in results_df.columns
