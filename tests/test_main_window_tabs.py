import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from pyama_pro.main_window import MainWindow
from pyama_pro.statistics.detail import StatisticsDetailPanel
from pyama_pro.statistics.load import StatisticsLoadPanel


def _write_analysis_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    pd.DataFrame(rows, columns=["time", "fov", "cell", "value"]).to_csv(
        path, index=False
    )


def test_main_window_has_modeling_and_statistics_tabs() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Processing",
        "Statistics",
        "Modeling",
        "Visualization",
    ]

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_main_window_loads_non_processing_tabs_lazily() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert window.processing_tab is not None
    assert window.statistics_tab is None
    assert window.modeling_tab is None
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(1)
    app.processEvents()
    assert window.statistics_tab is not None
    assert window.modeling_tab is None

    window.tabs.setCurrentIndex(2)
    app.processEvents()
    assert window.modeling_tab is not None
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(3)
    app.processEvents()
    assert window.visualization_tab is not None

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_tab_uses_dedicated_panels() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()
    window.tabs.setCurrentIndex(1)
    app.processEvents()

    assert window.statistics_tab is not None
    assert window.statistics_tab._load_panel is not None
    assert window.statistics_tab._detail_panel is not None
    assert window.statistics_tab._comparison_panel is not None

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_processing_config_no_longer_exposes_batch_size() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert window.processing_tab is not None
    assert window.processing_tab._input_panel is not None
    assert window.processing_tab._output_panel is not None
    assert not hasattr(window.processing_tab._output_panel._param_panel, "_use_manual_params")
    assert not window.processing_tab._output_panel._param_panel._param_table.isHidden()
    param_names = window.processing_tab._output_panel._param_panel._param_names
    assert "batch_size" not in param_names

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_detail_panel_populates_first_sample_immediately() -> None:
    app = QApplication.instance() or QApplication([])

    panel = StatisticsDetailPanel()
    results_df = pd.DataFrame(
        [
            {
                "sample": "sample_a",
                "fov": 0,
                "cell": 1,
                "success": True,
                "auc": 2.5,
            }
        ]
    )
    trace_df = pd.DataFrame(
        [
            {"fov": 0, "cell": 1, "time": 0.0, "value": 1.0},
            {"fov": 0, "cell": 1, "time": 1.0, "value": 2.0},
        ]
    ).set_index(["fov", "cell"])

    panel.set_results(
        results_df,
        {"sample_a": trace_df},
        "auc",
        normalize_by_area=False,
    )

    assert panel._selected_sample == "sample_a"
    assert panel._trace_list.count() == 1
    assert panel._stats_label.text().startswith("Sample sample_a:")

    panel.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_load_panel_enables_area_normalization_only_for_complete_samples(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])

    mixed_folder = tmp_path / "mixed"
    mixed_folder.mkdir()
    _write_analysis_csv(
        mixed_folder / "sample_a_intensity_ch_1.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "sample_a_area_ch_0.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "sample_b_intensity_ch_1.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )

    complete_folder = tmp_path / "complete"
    complete_folder.mkdir()
    _write_analysis_csv(
        complete_folder / "sample_a_intensity_ch_1.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        complete_folder / "sample_a_area_ch_0.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )

    panel = StatisticsLoadPanel()

    assert panel._normalize_checkbox.isEnabled() is False

    panel._load_folder(mixed_folder)
    assert panel._normalize_checkbox.isEnabled() is False
    assert panel._normalize_checkbox.isChecked() is False

    panel._load_folder(complete_folder)
    assert panel._normalize_checkbox.isEnabled() is True

    panel.close()
    if QApplication.instance() is app:
        app.processEvents()


