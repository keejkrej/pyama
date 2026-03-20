from pathlib import Path

from pyama.io.config import get_trace_csv_path, scan_processing_results


def _write_traces_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def test_scan_processing_results_discovers_fovs_and_channels(tmp_path: Path) -> None:
    fov0 = tmp_path / "fov_000"
    fov1 = tmp_path / "fov_001"
    fov0.mkdir()
    fov1.mkdir()

    (fov0 / "demo_fov_000_pc_ch_0.npy").write_bytes(b"")
    (fov0 / "demo_fov_000_seg_labeled_ch_0.npy").write_bytes(b"")
    (fov0 / "demo_fov_000_fl_ch_1.npy").write_bytes(b"")
    (fov1 / "demo_fov_001_fl_corrected_ch_2.npy").write_bytes(b"")

    _write_traces_csv(
        fov0 / "demo_fov_000_traces.csv",
        "frame,fov,cell,good,area_ch_0,intensity_ch_1",
        ["0,0,1,True,10,100"],
    )
    _write_traces_csv(
        fov1 / "demo_fov_001_traces.csv",
        "frame,fov,cell,good,variance_ch_2",
        ["0,1,1,True,5"],
    )

    results = scan_processing_results(tmp_path)

    assert results["project_path"] == tmp_path
    assert results["n_fov"] == 2
    assert results["channels"]["pc"] == {"channel": 0, "features": ["area"]}
    assert results["channels"]["fl"] == [
        {"channel": 1, "features": ["intensity"]},
        {"channel": 2, "features": ["variance"]},
    ]
    assert get_trace_csv_path(results, 0) == fov0 / "demo_fov_000_traces.csv"
    assert get_trace_csv_path(results, 1) == fov1 / "demo_fov_001_traces.csv"
    assert "seg_labeled_ch_0" in results["fov_data"][0]
    assert "fl_corrected_ch_2" in results["fov_data"][1]


def test_scan_processing_results_ignores_partial_non_fov_dirs(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "ignore.txt").write_text("ignore", encoding="utf-8")

    fov0 = tmp_path / "fov_000"
    fov0.mkdir()
    _write_traces_csv(
        fov0 / "demo_fov_000_traces.csv",
        "frame,fov,cell,good,mean_ch_1",
        ["0,0,1,True,10"],
    )

    results = scan_processing_results(tmp_path)

    assert results["n_fov"] == 1
    assert sorted(results["fov_data"]) == [0]
    assert results["channels"]["pc"] is None
    assert results["channels"]["fl"] == [{"channel": 1, "features": ["mean"]}]


def test_scan_processing_results_prefers_non_inspected_traces_entry(tmp_path: Path) -> None:
    fov0 = tmp_path / "fov_000"
    fov0.mkdir()
    _write_traces_csv(
        fov0 / "demo_fov_000_traces.csv",
        "frame,fov,cell,good,intensity_ch_1",
        ["0,0,1,True,10"],
    )
    _write_traces_csv(
        fov0 / "demo_fov_000_traces_inspected.csv",
        "frame,fov,cell,good,intensity_ch_1",
        ["0,0,1,True,11"],
    )

    results = scan_processing_results(tmp_path)

    assert get_trace_csv_path(results, 0) == fov0 / "demo_fov_000_traces.csv"
