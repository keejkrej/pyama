from pathlib import Path

from pyama.io.results import scan_processing_results
from pyama.io.traces import (
    collect_position_trace_files,
    infer_channel_feature_config,
    load_trace_bundle,
    write_trace_quality_update,
)


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


def test_infer_channel_feature_config_returns_empty_for_no_traces(
    tmp_path: Path,
) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h",
        ["0,1,0,True,0,0,1,1"],
    )

    results = scan_processing_results(tmp_path)

    assert infer_channel_feature_config(results) == []


def test_load_trace_bundle_reads_cells(tmp_path: Path) -> None:
    trace_path = tmp_path / "traces" / "position_0.csv"
    _write_traces_csv(
        trace_path,
        "position,roi,frame,is_good,x,y,w,h,area_c0,intensity_total_c1",
        [
            "0,7,0,True,1,2,3,4,10,100",
            "0,7,1,False,1,2,3,4,11,101",
        ],
    )

    bundle = load_trace_bundle(trace_path)

    assert bundle["resolved_path"] == str(trace_path)
    assert bundle["feature_options"] == ["area_c0", "intensity_total_c1"]
    cells = bundle["cells"]
    assert cells["7"]["quality"] is True
    assert cells["7"]["features"]["frame"] == [0, 1]
    assert cells["7"]["features"]["area_c0"] == [10, 11]


def test_write_trace_quality_update_writes_inspected_csv(tmp_path: Path) -> None:
    trace_path = tmp_path / "traces" / "position_0.csv"
    _write_traces_csv(
        trace_path,
        "position,roi,frame,is_good,x,y,w,h,area_c0",
        [
            "0,1,0,True,0,0,1,1,10",
            "0,2,0,True,0,0,1,1,11",
        ],
    )

    save_path = write_trace_quality_update(trace_path, {"1": False, "2": True})

    assert save_path == tmp_path / "traces" / "position_0_inspected.csv"
    saved_text = save_path.read_text(encoding="utf-8")
    assert "0,1,0,False,0,0,1,1,10" in saved_text
    assert "0,2,0,True,0,0,1,1,11" in saved_text
