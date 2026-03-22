from pathlib import Path

from pyama.io.results import get_trace_csv_path, scan_processing_results
from pyama.types.processing import Channels


def _write_traces_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def test_scan_processing_results_discovers_fovs_and_channels(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()

    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0,intensity_total_c1",
        ["0,1,0,True,0,0,1,1,10,100"],
    )
    _write_traces_csv(
        traces_dir / "position_1.csv",
        "position,roi,frame,is_good,x,y,w,h,variance_c2",
        ["1,1,0,True,0,0,1,1,5"],
    )

    results = scan_processing_results(tmp_path)

    assert results.project_path == tmp_path
    assert results.n_positions == 2
    assert results.channels == Channels(
        pc={0: ["area"]},
        fl={1: ["intensity_total"], 2: ["variance"]},
    )
    assert get_trace_csv_path(results, 0) == traces_dir / "position_0.csv"
    assert get_trace_csv_path(results, 1) == traces_dir / "position_1.csv"
    assert get_trace_csv_path(results, 0, prefer_inspected=True) == traces_dir / "position_0.csv"
    assert results.position_data[0]["traces"] == traces_dir / "position_0.csv"
    assert results.position_data[1]["traces"] == traces_dir / "position_1.csv"


def test_scan_processing_results_ignores_partial_non_fov_dirs(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "ignore.txt").write_text("ignore", encoding="utf-8")

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,mean_c1",
        ["0,1,0,True,0,0,1,1,10"],
    )

    results = scan_processing_results(tmp_path)

    assert results.n_positions == 1
    assert sorted(results.position_data) == [0]
    assert results.channels is None


def test_scan_processing_results_prefers_non_inspected_traces_entry(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    inspected_dir = traces_dir / "inspected"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,intensity_total_c1",
        ["0,1,0,True,0,0,1,1,10"],
    )
    _write_traces_csv(
        inspected_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,intensity_total_c1",
        ["0,1,0,True,0,0,1,1,11"],
    )

    results = scan_processing_results(tmp_path)

    assert get_trace_csv_path(results, 0) == traces_dir / "position_0.csv"
    assert get_trace_csv_path(results, 0, prefer_inspected=True) == inspected_dir / "position_0.csv"
