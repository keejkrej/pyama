from pathlib import Path

import pandas as pd
import yaml

from pyama.apps.processing.merge import normalize_samples, parse_positions_field, run_merge_traces
from pyama.io.traces import infer_channel_feature_config
from pyama.io.results import scan_processing_results


def _write_processing_results(base_dir: Path, csv_path: Path) -> Path:
    traces_dir = base_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    dest = traces_dir / csv_path.name
    dest.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    return traces_dir


def test_parse_positions_field_uses_slice_syntax_only() -> None:
    assert parse_positions_field("0:3") == [0, 1, 2]


def test_run_merge_traces_writes_traces_merged_with_position_roi_columns(tmp_path: Path) -> None:
    samples = normalize_samples([{"name": "sample", "positions": "0"}])

    csv_path = tmp_path / "position_0.csv"
    df = pd.DataFrame(
        {
            "position": [0, 0],
            "frame": [0, 1],
            "roi": [1, 1],
            "is_good": [True, True],
            "x": [0.0, 0.0],
            "y": [0.0, 0.0],
            "w": [1.0, 1.0],
            "h": [1.0, 1.0],
            "area_c0": [10.0, 12.0],
            "intensity_c1": [100.0, 110.0],
        }
    )
    df.to_csv(csv_path, index=False)

    _write_processing_results(tmp_path, csv_path)
    sample_yaml = tmp_path / "samples.yaml"
    sample_yaml.write_text(
        yaml.safe_dump(
            {
                "samples": [
                    {"name": sample.name, "positions": list(sample.positions)}
                    for sample in samples
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = run_merge_traces(tmp_path, sample_yaml)

    assert summary["merged_positions"] == 1
    assert summary["merged_files"] == 2

    output_dir = tmp_path / "traces_merged"
    pc_output = output_dir / "area_c0" / "sample.csv"
    fl_output = output_dir / "intensity_c1" / "sample.csv"

    assert pc_output.exists()
    assert fl_output.exists()
    assert list(pd.read_csv(pc_output).columns) == ["position", "roi", "frame", "value"]
    assert list(pd.read_csv(fl_output).columns) == ["position", "roi", "frame", "value"]


def test_infer_channel_feature_config_reads_position_outputs(tmp_path: Path) -> None:
    csv_path = tmp_path / "position_0.csv"
    csv_content = (
        "frame,roi,is_good,x,y,w,h,area_c0,perimeter_c0,intensity_c1,mean_c1,variance_c2\n"
        "0,1,True,0,0,1,1,10,15,100,50,5\n"
        "1,1,True,0,0,1,1,12,16,110,55,6\n"
    )
    csv_path.write_text(csv_content, encoding="utf-8")

    traces_dir = tmp_path / "traces"
    traces_dir.mkdir()
    scanned_csv = traces_dir / csv_path.name
    scanned_csv.write_text(csv_content, encoding="utf-8")

    proc_results = scan_processing_results(tmp_path)
    config = infer_channel_feature_config(proc_results)

    assert config[0][1] == ["area", "perimeter"]
    assert config[1][1] == ["intensity", "mean"]
    assert config[2][1] == ["variance"]
