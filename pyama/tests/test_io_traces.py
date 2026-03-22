from pathlib import Path

from pyama.io.results import scan_processing_results
from pyama.io.traces import collect_position_trace_files, infer_channel_feature_config


def _write_traces_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")

def test_collect_position_trace_files_prefers_inspected(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(traces_dir / "position_0.csv", "frame", ["0"])
    _write_traces_csv(traces_dir / "inspected" / "position_0.csv", "frame", ["1"])
    _write_traces_csv(traces_dir / "position_1.csv", "frame", ["0"])

    selected = collect_position_trace_files(traces_dir)

    assert selected[0] == traces_dir / "inspected" / "position_0.csv"
    assert selected[1] == traces_dir / "position_1.csv"


def test_collect_position_trace_files_filters_positions(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(traces_dir / "position_0.csv", "frame", ["0"])
    _write_traces_csv(traces_dir / "position_2.csv", "frame", ["0"])

    selected = collect_position_trace_files(traces_dir, position_ids={2})

    assert selected == {2: traces_dir / "position_2.csv"}


def test_infer_channel_feature_config_extracts_features(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0,intensity_total_c1,variance_c2",
        ["0,1,0,True,0,0,1,1,10,100,5"],
    )

    results = scan_processing_results(tmp_path)

    assert infer_channel_feature_config(results) == [
        (0, ["area"]),
        (1, ["intensity_total"]),
        (2, ["variance"]),
    ]


def test_infer_channel_feature_config_returns_empty_for_no_traces(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h",
        ["0,1,0,True,0,0,1,1"],
    )

    results = scan_processing_results(tmp_path)

    assert infer_channel_feature_config(results) == []
