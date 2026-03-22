from pathlib import Path

import pytest

from pyama.io.results import get_trace_csv_path, scan_processing_results
from pyama.types.processing import Channels, ProcessingConfig
from pyama.io.config import save_config


def _write_traces_csv(path: Path, header: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def test_scan_processing_results_infers_no_channels_without_phase_contrast(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,mean_c1",
        ["0,1,0,True,0,0,1,1,10"],
    )

    results = scan_processing_results(tmp_path)

    assert results.channels is None


def test_scan_processing_results_prefers_config_channels(tmp_path: Path) -> None:
    save_config(
        ProcessingConfig(
            channels=Channels(pc={0: ["area"]}, fl={2: ["mean"]}),
        ),
        tmp_path / "processing_config.yaml",
    )
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0,variance_c3",
        ["0,1,0,True,0,0,1,1,10,5"],
    )

    results = scan_processing_results(tmp_path)

    assert results.channels == Channels(pc={0: ["area"]}, fl={2: ["mean"]})
    assert results.config_path == tmp_path / "processing_config.yaml"
    assert results.traces_dir == traces_dir


def test_scan_processing_results_raises_when_no_outputs_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_processing_results(tmp_path)


def test_get_trace_csv_path_returns_none_for_missing_position(tmp_path: Path) -> None:
    traces_dir = tmp_path / "traces"
    _write_traces_csv(
        traces_dir / "position_0.csv",
        "position,roi,frame,is_good,x,y,w,h,area_c0",
        ["0,1,0,True,0,0,1,1,10"],
    )

    results = scan_processing_results(tmp_path)

    assert get_trace_csv_path(results, 1) is None
