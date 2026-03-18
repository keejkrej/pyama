import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
from PySide6.QtWidgets import QApplication

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.main_window import MainWindow
from pyama_gui.modeling.view import ModelingView
from pyama_gui.processing.view import ProcessingView
from pyama_gui.processing.view_model import ProcessingViewModel
from pyama_gui.statistics.view import StatisticsView
from pyama_gui.statistics.view_model import StatisticsViewModel
from pyama_gui.visualization.view import VisualizationView
from pyama_gui.visualization.view_model import VisualizationViewModel


def _write_analysis_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    pd.DataFrame(rows, columns=["time", "fov", "cell", "value"]).to_csv(
        path, index=False
    )


def test_main_window_has_consolidated_tabs() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Processing",
        "Statistics",
        "Modeling",
        "Visualization",
    ]
    assert isinstance(window.processing_tab, ProcessingView)

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_main_window_loads_non_processing_tabs_lazily() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert isinstance(window.processing_tab, ProcessingView)
    assert window.statistics_tab is None
    assert window.modeling_tab is None
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(1)
    app.processEvents()
    assert isinstance(window.statistics_tab, StatisticsView)
    assert window.modeling_tab is None

    window.tabs.setCurrentIndex(2)
    app.processEvents()
    assert isinstance(window.modeling_tab, ModelingView)
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(3)
    app.processEvents()
    assert isinstance(window.visualization_tab, VisualizationView)

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_app_view_model_tracks_workspace_and_busy() -> None:
    app_view_model = AppViewModel()
    workspace = Path("/tmp/example-workspace")

    assert app_view_model.workspace_dir is None
    assert app_view_model.busy is False
    assert app_view_model.status_message == "Ready"

    app_view_model.set_workspace_dir(workspace)
    app_view_model.set_status_message("Loading")
    app_view_model.begin_busy()
    app_view_model.begin_busy()
    app_view_model.end_busy()

    assert app_view_model.workspace_dir == workspace
    assert app_view_model.status_message == "Loading"
    assert app_view_model.busy is True

    app_view_model.end_busy()
    assert app_view_model.busy is False


def test_processing_view_model_reports_missing_inputs() -> None:
    app_view_model = AppViewModel()
    view_model = ProcessingViewModel(app_view_model)

    view_model.run_workflow()

    assert app_view_model.status_message == "Select a microscopy file first."


def test_statistics_view_model_enables_area_normalization_only_for_complete_samples(
    tmp_path: Path,
) -> None:
    mixed_folder = tmp_path / "merge_output"
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

    app_view_model = AppViewModel()
    app_view_model.set_workspace_dir(tmp_path)
    view_model = StatisticsViewModel(app_view_model)

    assert view_model.normalization_available is False
    assert view_model.normalize_by_area is False

    complete_folder = tmp_path / "complete_workspace" / "merge_output"
    complete_folder.mkdir(parents=True)
    _write_analysis_csv(
        complete_folder / "sample_a_intensity_ch_1.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        complete_folder / "sample_a_area_ch_0.csv",
        [{"time": 0.0, "fov": 0, "cell": 0, "value": 1.0}],
    )

    app_view_model.set_workspace_dir(tmp_path / "complete_workspace")

    assert view_model.normalization_available is True


def test_visualization_view_model_loads_workspace_on_workspace_change(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()

    app_view_model = AppViewModel()
    view_model = VisualizationViewModel(app_view_model)

    app_view_model.set_workspace_dir(workspace)

    assert view_model.workspace_dir == workspace
    assert view_model.running is True or "Workspace:" in view_model.details_text


def test_statistics_view_model_populates_first_sample_immediately() -> None:
    app = QApplication.instance() or QApplication([])
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

    view_model = StatisticsViewModel(AppViewModel())
    view_model._results_df = results_df
    view_model._traces_by_sample = {"sample_a": trace_df}
    view_model._selected_sample = "sample_a"
    view_model._selected_metric = "auc"
    view_model.set_selected_sample("sample_a")

    assert view_model.selected_sample == "sample_a"
    assert view_model.visible_trace_ids == [(0, 1)]
    assert view_model.detail_stats_text.startswith("Sample sample_a:")

    if QApplication.instance() is app:
        app.processEvents()
