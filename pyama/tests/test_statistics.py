from pathlib import Path

import numpy as np
import pandas as pd

from pyama.apps.statistics.discovery import discover_sample_pairs
from pyama.apps.statistics.normalization import load_normalized_sample
from pyama.apps.statistics.service import run_folder_statistics
from pyama.io.csv import DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES, load_analysis_csv
from pyama.types.statistics import SamplePair


def _write_analysis_csv(path: Path, rows: list[dict]) -> None:
    pd.DataFrame(rows, columns=["frame", "fov", "cell", "value"]).to_csv(
        path, index=False
    )


def _write_sample_pair(
    folder: Path,
    sample_name: str,
    intensity_rows: list[dict],
    area_rows: list[dict],
) -> None:
    _write_analysis_csv(folder / f"{sample_name}_intensity_ch_1.csv", intensity_rows)
    _write_analysis_csv(folder / f"{sample_name}_area_ch_0.csv", area_rows)


def test_discover_sample_pairs_returns_intensity_samples_with_optional_area(
    tmp_path: Path,
) -> None:
    _write_sample_pair(
        tmp_path,
        "sample_a",
        [{"frame": 0, "fov": 0, "cell": 0, "value": 2.0}],
        [{"frame": 0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        tmp_path / "sample_b_intensity_ch_1.csv",
        [{"frame": 0, "fov": 0, "cell": 0, "value": 3.0}],
    )
    _write_analysis_csv(
        tmp_path / "sample_c_area_ch_0.csv",
        [{"frame": 0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        tmp_path / "statistics_auc_normalized.csv",
        [{"frame": 0, "fov": 0, "cell": 0, "value": 1.0}],
    )

    pairs = discover_sample_pairs(tmp_path)

    assert [pair.sample_name for pair in pairs] == ["sample_a", "sample_b"]
    assert pairs[0].area_csv is not None
    assert pairs[1].area_csv is None


def test_load_normalized_sample_applies_area_median_filter(tmp_path: Path) -> None:
    pair = SamplePair(
        sample_name="sample",
        intensity_csv=tmp_path / "sample_intensity_ch_1.csv",
        area_csv=tmp_path / "sample_area_ch_0.csv",
    )
    _write_analysis_csv(
        pair.intensity_csv,
        [
            {"frame": frame, "fov": 0, "cell": 0, "value": float(value)}
            for frame, value in enumerate([10, 20, 30, 40, 50])
        ],
    )
    _write_analysis_csv(
        pair.area_csv,
        [
            {"frame": frame, "fov": 0, "cell": 0, "value": float(value)}
            for frame, value in enumerate([10, 10, 100, 10, 10])
        ],
    )

    normalized_df = load_normalized_sample(pair, area_filter_size=3).reset_index()

    np.testing.assert_allclose(normalized_df["value"].to_numpy(), [1, 2, 3, 4, 5])


def test_load_normalized_sample_marks_non_positive_area_invalid(tmp_path: Path) -> None:
    pair = SamplePair(
        sample_name="sample",
        intensity_csv=tmp_path / "sample_intensity_ch_1.csv",
        area_csv=tmp_path / "sample_area_ch_0.csv",
    )
    _write_analysis_csv(
        pair.intensity_csv,
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )
    _write_analysis_csv(
        pair.area_csv,
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 0.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )

    normalized_df = load_normalized_sample(pair, area_filter_size=1).reset_index()

    assert normalized_df.loc[1, "value"] != normalized_df.loc[1, "value"]


def test_load_normalized_sample_can_skip_area_normalization(tmp_path: Path) -> None:
    pair = SamplePair(
        sample_name="sample",
        intensity_csv=tmp_path / "sample_intensity_ch_1.csv",
        area_csv=tmp_path / "sample_area_ch_0.csv",
    )
    _write_analysis_csv(
        pair.intensity_csv,
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 4.0},
        ],
    )
    _write_analysis_csv(
        pair.area_csv,
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 10.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 10.0},
        ],
    )

    trace_df = load_normalized_sample(
        pair, area_filter_size=3, normalize_by_area=False
    ).reset_index()

    np.testing.assert_allclose(trace_df["value"].to_numpy(), [2.0, 4.0])


def test_run_folder_statistics_auc_writes_expected_metrics(tmp_path: Path) -> None:
    _write_sample_pair(
        tmp_path,
        "sample_a",
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 0.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 4.0},
        ],
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )
    _write_sample_pair(
        tmp_path,
        "sample_b",
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )

    results_df, normalized_by_sample, output_path = run_folder_statistics(
        tmp_path, "auc", area_filter_size=1
    )

    assert sorted(normalized_by_sample) == ["sample_a", "sample_b"]
    assert output_path.name == "statistics_auc_normalized.csv"
    assert output_path.exists()

    result_map = {
        row["sample"]: row["auc"]
        for _, row in results_df.sort_values("sample").iterrows()
    }
    assert result_map["sample_a"] == 2.0 * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES
    assert result_map["sample_b"] == 2.0 * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES


def test_run_folder_statistics_auc_can_use_raw_intensity(tmp_path: Path) -> None:
    _write_sample_pair(
        tmp_path,
        "sample",
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 0.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 4.0},
        ],
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )

    results_df, traces_by_sample, output_path = run_folder_statistics(
        tmp_path,
        "auc",
        normalize_by_area=False,
        area_filter_size=1,
    )

    assert sorted(traces_by_sample) == ["sample"]
    assert output_path.name == "statistics_auc_raw.csv"
    assert output_path.exists()

    row = results_df.iloc[0]
    assert row["normalization_mode"] == "raw_intensity"
    assert row["source_area_file"] == ""
    assert float(row["auc"]) == 4.0 * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES


def test_run_folder_statistics_normalized_requires_area_for_every_sample(
    tmp_path: Path,
) -> None:
    _write_analysis_csv(
        tmp_path / "sample_intensity_ch_1.csv",
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 1.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
        ],
    )

    try:
        run_folder_statistics(
            tmp_path,
            "auc",
            normalize_by_area=True,
            area_filter_size=1,
        )
    except ValueError as exc:
        assert "requires an area CSV for every sample" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected normalization to fail without area CSV")


def test_run_folder_statistics_onset_fits_and_marks_short_traces(
    tmp_path: Path,
) -> None:
    normalized_rows = []
    for frame in [0, 6, 12, 18, 24]:
        time = frame * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES
        normalized_rows.append(
            {
                "frame": frame,
                "fov": 0,
                "cell": 0,
                "value": 0.5 + (2.0 / 60.0) * max(time - 60.0, 0.0),
            }
        )
    for frame in [0, 6, 12]:
        time = frame * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES
        normalized_rows.append(
            {
                "frame": frame,
                "fov": 0,
                "cell": 1,
                "value": 1.0 + (1.0 / 60.0) * max(time - 30.0, 0.0),
            }
        )

    intensity_rows = []
    area_rows = []
    for row in normalized_rows:
        intensity_rows.append({**row, "value": row["value"] * 2.0})
        area_rows.append({**row, "value": 2.0})

    _write_sample_pair(tmp_path, "sample", intensity_rows, area_rows)

    results_df, _, output_path = run_folder_statistics(
        tmp_path,
        "onset_shifted_relu",
        fit_window_min=240.0,
        area_filter_size=1,
    )

    assert output_path.name == "statistics_onset_shifted_relu_normalized.csv"
    assert output_path.exists()

    good_row = results_df.loc[results_df["cell"] == 0].iloc[0]
    short_row = results_df.loc[results_df["cell"] == 1].iloc[0]

    assert bool(good_row["success"]) is True
    assert abs(float(good_row["onset_time_min"]) - 60.0) < 1e-2
    assert abs(float(good_row["slope_min"]) - (2.0 / 60.0)) < 1e-2
    assert abs(float(good_row["offset"]) - 0.5) < 1e-2
    assert float(good_row["r_squared"]) > 0.99

    assert bool(short_row["success"]) is False
    assert int(short_row["n_points"]) == 3


def test_run_folder_statistics_onset_allows_negative_onset(
    tmp_path: Path,
) -> None:
    normalized_rows = []
    for frame in [0, 6, 12, 18, 24]:
        time = frame * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES
        normalized_rows.append(
            {
                "frame": frame,
                "fov": 0,
                "cell": 0,
                "value": 0.5 + (2.0 / 60.0) * max(time + 15.0, 0.0),
            }
        )

    intensity_rows = []
    area_rows = []
    for row in normalized_rows:
        intensity_rows.append({**row, "value": row["value"] * 2.0})
        area_rows.append({**row, "value": 2.0})

    _write_sample_pair(tmp_path, "sample", intensity_rows, area_rows)

    results_df, _, _ = run_folder_statistics(
        tmp_path,
        "onset_shifted_relu",
        fit_window_min=240.0,
        area_filter_size=1,
    )

    row = results_df.iloc[0]

    assert bool(row["success"]) is True
    assert float(row["onset_time_min"]) < 0.0
    assert abs(float(row["onset_time_min"]) + 15.0) < 1e-2
    assert abs(float(row["slope_min"]) - (2.0 / 60.0)) < 1e-2
    assert abs(float(row["offset"]) - 0.5) < 1e-2


def test_load_analysis_csv_derives_time_min_from_frame(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    _write_analysis_csv(
        csv_path,
        [
            {"frame": 0, "fov": 0, "cell": 0, "value": 1.0},
            {"frame": 1, "fov": 0, "cell": 0, "value": 2.0},
            {"frame": 2, "fov": 0, "cell": 0, "value": 3.0},
        ],
    )

    df = load_analysis_csv(csv_path).reset_index()

    assert pd.api.types.is_integer_dtype(df["frame"])
    np.testing.assert_allclose(
        df["time_min"].to_numpy(),
        [
            0.0,
            DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES,
            2.0 * DEFAULT_ANALYSIS_FRAME_INTERVAL_MINUTES,
        ],
    )


def test_load_analysis_csv_rejects_legacy_time_schema(tmp_path: Path) -> None:
    csv_path = tmp_path / "legacy.csv"
    pd.DataFrame(
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
        columns=["time", "fov", "cell", "value"],
    ).to_csv(csv_path, index=False)

    try:
        load_analysis_csv(csv_path)
    except ValueError as exc:
        assert "expected 'frame' column" in str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected legacy time-based CSV to be rejected")
