import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton

from pyama.io.zarr import open_raw_zarr, open_rois_zarr
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.modeling.view_model import ModelingViewModel
from pyama_gui.main_window import MainWindow
from pyama_gui.services import FileDialogService
from pyama_gui.components import PyQtGraphImageView
from pyama_gui.apps.modeling.view import ModelingView
from pyama_gui.apps.processing.view import ProcessingView
from pyama_gui.apps.processing.view_model import ProcessingViewModel
from pyama_gui.apps.statistics.view import StatisticsView
from pyama_gui.apps.statistics.view_model import StatisticsViewModel
from pyama_gui.apps.visualization.view import VisualizationView
from pyama_gui.apps.visualization.view_model import VisualizationViewModel


def _write_analysis_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    pd.DataFrame(rows, columns=["frame", "position", "roi", "value"]).to_csv(
        path, index=False
    )


def _write_roi_mask(
    workspace: Path,
    *,
    position_id: int,
    channel_id: int,
    roi_id: int,
    frame_idx: int,
    bbox: tuple[int, int, int, int],
    mask: np.ndarray | None,
) -> None:
    store = open_rois_zarr(workspace / "rois.zarr", mode="a")
    roi_ids = np.array([roi_id], dtype=np.int32)
    roi_bboxes = np.array([[bbox]], dtype=np.int32)
    roi_is_present = np.array([[True]], dtype=bool)
    store.write_roi_ids(position_id, roi_ids)
    store.write_roi_bboxes(position_id, roi_bboxes)
    store.write_roi_is_present(position_id, roi_is_present)
    if mask is not None:
        store.write_seg_mask_frame(position_id, channel_id, roi_id, frame_idx, mask)


class StubDialogService(FileDialogService):
    def __init__(
        self,
        *,
        directory: Path | None = None,
        open_file: Path | None = None,
        save_file: Path | None = None,
    ) -> None:
        self.directory = directory
        self.open_file = open_file
        self.save_file = save_file

    def select_directory(self, caption: str, directory: str) -> Path | None:
        return self.directory

    def select_open_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        return self.open_file

    def select_save_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        return self.save_file


def test_main_window_has_consolidated_tabs() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert window.workspace_bar._path_label.text() == "Not set"
    assert window.workspace_bar.change_button.text() == "Set Workspace..."
    assert not window.menuBar().actions()
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


def test_main_window_startup_prompt_sets_workspace() -> None:
    app = QApplication.instance() or QApplication([])
    workspace = Path("/tmp/startup-workspace")

    window = MainWindow(dialog_service=StubDialogService(directory=workspace))
    window.prompt_for_workspace_on_startup()

    assert window.app_view_model.workspace_dir == workspace
    assert (
        window.app_view_model.status_message == f"Workspace folder set to {workspace}"
    )
    assert window.workspace_bar._path_label.text() == str(workspace)
    assert window.workspace_bar.change_button.text() == "Change..."

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_workspace_bar_button_sets_workspace() -> None:
    app = QApplication.instance() or QApplication([])
    workspace = Path("/tmp/workspace-bar-workspace")

    window = MainWindow(dialog_service=StubDialogService(directory=workspace))
    window.workspace_bar.change_button.click()

    assert window.app_view_model.workspace_dir == workspace
    assert window.workspace_bar._path_label.text() == str(workspace)
    assert window.workspace_bar.change_button.text() == "Change..."

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_tab_loads_existing_workspace_when_lazy_created(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    workspace = tmp_path / "workspace"
    traces_merged = workspace / "traces_merged"
    traces_merged.mkdir(parents=True)
    _write_analysis_csv(
        traces_merged / "sample_a_intensity_ch_1.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        traces_merged / "sample_a_area_ch_0.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )

    window = MainWindow()
    window.app_view_model.set_workspace_dir(workspace)
    window.tabs.setCurrentIndex(1)
    app.processEvents()

    assert isinstance(window.statistics_tab, StatisticsView)
    assert [
        window.statistics_tab._sample_list.item(i).text()
        for i in range(window.statistics_tab._sample_list.count())
    ] == ["sample_a"]

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_visualization_tab_loads_existing_workspace_when_lazy_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = QApplication.instance() or QApplication([])
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )

    class _Handle:
        pass

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.WorkerHandle",
        _Handle,
        raising=False,
    )
    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.scan_processing_results",
        lambda path: type(
            "Result",
            (),
            {
                "to_dict": staticmethod(
                    lambda: {
                        "project_path": str(path),
                        "n_positions": 1,
                        "position_data": {
                            0: {
                                "raw_ch_0": f"{path / 'raw.zarr'}::position/0/channel/0/raw"
                            }
                        },
                    }
                )
            },
        )(),
    )

    window = MainWindow()
    window.app_view_model.set_workspace_dir(workspace)
    window.tabs.setCurrentIndex(3)
    app.processEvents()

    assert isinstance(window.visualization_tab, VisualizationView)
    assert window.visualization_tab.view_model.workspace_dir == workspace
    assert "Project Path:" in window.visualization_tab.view_model.details_text
    assert isinstance(window.visualization_tab._image_viewer, PyQtGraphImageView)

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_app_view_model_tracks_workspace_and_busy() -> None:
    app_view_model = AppViewModel(dialog_service=StubDialogService())
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
    app_view_model = AppViewModel(dialog_service=StubDialogService())
    view_model = ProcessingViewModel(app_view_model)

    view_model.run_workflow()

    assert app_view_model.status_message == "Select a microscopy file first."


def test_statistics_view_model_enables_area_normalization_only_for_complete_samples(
    tmp_path: Path,
) -> None:
    mixed_folder = tmp_path / "traces_merged"
    mixed_folder.mkdir()
    _write_analysis_csv(
        mixed_folder / "sample_a_intensity_ch_1.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "sample_a_area_ch_0.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "sample_b_intensity_ch_1.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )

    app_view_model = AppViewModel()
    app_view_model.set_workspace_dir(tmp_path)
    view_model = StatisticsViewModel(app_view_model)

    assert view_model.normalization_available is False
    assert view_model.normalize_by_area is False
    assert view_model.frame_interval_minutes == 10.0
    assert view_model.fit_window_min == 240.0

    complete_folder = tmp_path / "complete_workspace" / "traces_merged"
    complete_folder.mkdir(parents=True)
    _write_analysis_csv(
        complete_folder / "sample_a_intensity_ch_1.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        complete_folder / "sample_a_area_ch_0.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )

    app_view_model.set_workspace_dir(tmp_path / "complete_workspace")

    assert view_model.normalization_available is True


def test_mvvm_dialog_boundary_removed_from_widgets() -> None:
    paths = [
        Path("pyama-gui/src/pyama_gui/main_window.py"),
        Path("pyama-gui/src/pyama_gui/apps/processing/view.py"),
        Path("pyama-gui/src/pyama_gui/apps/modeling/view.py"),
        Path("pyama-gui/src/pyama_gui/apps/visualization/view.py"),
    ]
    for path in paths:
        assert "QFileDialog" not in path.read_text()


def test_gui_feature_packages_only_live_under_apps() -> None:
    repo_root = Path("pyama-gui/src/pyama_gui")
    assert not (repo_root / "processing").exists()
    assert not (repo_root / "statistics").exists()
    assert not (repo_root / "modeling").exists()
    assert not (repo_root / "visualization").exists()


def test_visualization_view_model_loads_workspace_on_workspace_change(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )
    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.scan_processing_results",
        lambda path: type(
            "Result",
            (),
            {
                "to_dict": staticmethod(
                    lambda: {
                        "project_path": str(path),
                        "n_positions": 0,
                        "position_data": {},
                    }
                )
            },
        )(),
    )

    app_view_model = AppViewModel()
    view_model = VisualizationViewModel(app_view_model)

    app_view_model.set_workspace_dir(workspace)

    assert view_model.workspace_dir == workspace
    assert "Project Path:" in view_model.details_text or view_model.details_text == ""


def test_visualization_view_model_loads_real_scanned_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    app = QApplication.instance() or QApplication([])
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()
    store = open_raw_zarr(workspace / "raw.zarr", mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=2,
        height=3,
        width=4,
    )
    dataset[:] = np.arange(24, dtype=np.uint16).reshape(2, 3, 4)
    traces_dir = workspace / "traces"
    traces_dir.mkdir()
    _write_roi_mask(
        workspace,
        position_id=0,
        channel_id=0,
        roi_id=1,
        frame_idx=0,
        bbox=(1, 0, 2, 2),
        mask=np.array([[True, True], [True, True]], dtype=bool),
    )
    pd.DataFrame(
        [
            {
                "position": 0,
                "roi": 1,
                "frame": 0,
                "is_good": True,
                "x": 1.0,
                "y": 2.0,
                "w": 3.0,
                "h": 4.0,
                "area_c0": 10.0,
            }
        ]
    ).to_csv(traces_dir / "position_0.csv", index=False)

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )

    app_view_model = AppViewModel()
    view_model = VisualizationViewModel(app_view_model)
    app_view_model.set_workspace_dir(workspace)
    view_model.set_selected_channels(["raw_ch_0"])
    view_model.start_visualization()

    assert view_model.state.current_image is not None
    assert view_model.state.current_image.shape == (3, 4)
    assert view_model.state.data_types == ["raw_ch_0"]
    assert view_model.state.trace_rows
    assert len(view_model.state.overlays) == 1
    assert view_model.state.overlays[0].properties["type"] == "polygon"

    if QApplication.instance() is app:
        app.processEvents()


def test_visualization_view_model_omits_overlays_without_rois_zarr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()
    store = open_raw_zarr(workspace / "raw.zarr", mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=1,
        height=3,
        width=4,
    )
    dataset[:] = np.arange(12, dtype=np.uint16).reshape(1, 3, 4)
    traces_dir = workspace / "traces"
    traces_dir.mkdir()
    pd.DataFrame(
        [
            {
                "position": 0,
                "roi": 1,
                "frame": 0,
                "is_good": True,
                "x": 1.0,
                "y": 2.0,
                "w": 3.0,
                "h": 4.0,
                "area_c0": 10.0,
            }
        ]
    ).to_csv(traces_dir / "position_0.csv", index=False)

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )

    view_model = VisualizationViewModel(AppViewModel())
    view_model.app_view_model.set_workspace_dir(workspace)
    view_model.set_selected_channels(["raw_ch_0"])
    view_model.start_visualization()

    assert view_model.state.current_image is not None
    assert view_model.state.overlays == []


def test_visualization_view_model_omits_overlay_when_mask_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()
    store = open_raw_zarr(workspace / "raw.zarr", mode="a")
    dataset = store.create_uint16_timeseries(
        "position/0/channel/0/raw",
        n_frames=1,
        height=3,
        width=4,
    )
    dataset[:] = np.arange(12, dtype=np.uint16).reshape(1, 3, 4)
    traces_dir = workspace / "traces"
    traces_dir.mkdir()
    _write_roi_mask(
        workspace,
        position_id=0,
        channel_id=0,
        roi_id=1,
        frame_idx=0,
        bbox=(1, 0, 2, 2),
        mask=None,
    )
    pd.DataFrame(
        [
            {
                "position": 0,
                "roi": 1,
                "frame": 0,
                "is_good": True,
                "x": 1.0,
                "y": 2.0,
                "w": 3.0,
                "h": 4.0,
                "area_c0": 10.0,
            }
        ]
    ).to_csv(traces_dir / "position_0.csv", index=False)

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )

    view_model = VisualizationViewModel(AppViewModel())
    view_model.app_view_model.set_workspace_dir(workspace)
    view_model.set_selected_channels(["raw_ch_0"])
    view_model.start_visualization()

    assert view_model.state.current_image is not None
    assert view_model.state.overlays == []


def test_visualization_view_routes_image_overlay_interactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    view = VisualizationView(AppViewModel())
    selected: list[str] = []
    toggled: list[str] = []

    monkeypatch.setattr(view.view_model, "select_trace", selected.append)
    monkeypatch.setattr(view.view_model, "toggle_trace_quality", toggled.append)

    view._image_viewer.overlay_clicked.emit("trace_7")
    view._image_viewer.overlay_right_clicked.emit("trace_7")

    assert selected == ["7"]
    assert toggled == ["7"]

    view.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_view_model_populates_first_sample_immediately() -> None:
    app = QApplication.instance() or QApplication([])
    results_df = pd.DataFrame(
        [
            {
                "sample": "sample_a",
                "position": 0,
                "roi": 1,
                "success": True,
                "auc": 2.5,
            }
        ]
    )
    trace_df = pd.DataFrame(
        [
            {"position": 0, "roi": 1, "frame": 0, "time_min": 0.0, "value": 1.0},
            {"position": 0, "roi": 1, "frame": 6, "time_min": 60.0, "value": 2.0},
        ]
    ).set_index(["position", "roi"])

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


def test_modeling_view_model_defaults_to_base_and_10_minute_interval() -> None:
    view_model = ModelingViewModel(AppViewModel())

    assert "base" in view_model.model_names
    assert view_model.model_type == "base"
    assert view_model.state.frame_interval_minutes == 10.0
    parameter_keys = [parameter.key for parameter in view_model.state.parameters]
    assert parameter_keys == [
        "protein_degradation_rate_min",
        "time_onset_min",
        "ktl_m0_min",
        "mrna_degradation_rate_min",
        "intensity_offset",
    ]
    protein_param = view_model.state.parameters[0]
    assert [option.key for option in protein_param.preset_options] == ["gfp", "dsred"]


def test_modeling_view_uses_updated_section_labels() -> None:
    app = QApplication.instance() or QApplication([])

    view = ModelingView(AppViewModel(dialog_service=StubDialogService()))

    group_titles = [group.title() for group in view.findChildren(QGroupBox)]
    button_texts = [button.text() for button in view.findChildren(QPushButton)]
    labels = [label.text() for label in view.findChildren(QLabel)]

    assert "Trace" in group_titles
    assert "Parameter" in group_titles
    assert "Fitted Traces" not in group_titles
    assert "Parameter Analysis" not in group_titles
    assert "Save Histogram" not in button_texts
    assert "Save Scatter Plot" not in button_texts
    assert "Single:" in labels
    assert "Double:" in labels

    view.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_modeling_parameter_plot_can_be_saved_from_right_click(tmp_path: Path) -> None:
    app = QApplication.instance() or QApplication([])
    save_path = tmp_path / "parameter_time_onset_min.png"
    dialog_service = StubDialogService(save_file=save_path)
    view = ModelingView(AppViewModel(dialog_service=dialog_service))

    view.view_model._results_df = pd.DataFrame(
        [
            {
                "position": 0,
                "roi": 1,
                "model_type": "base",
                "success": True,
                "r_squared": 0.95,
                "time_onset_min": 120.0,
                "mrna_degradation_rate_min": 0.001,
            },
            {
                "position": 0,
                "roi": 2,
                "model_type": "base",
                "success": True,
                "r_squared": 0.91,
                "time_onset_min": 140.0,
                "mrna_degradation_rate_min": 0.002,
            },
        ]
    )
    view.view_model._refresh_results_state()
    view._refresh_state()

    view._param_canvas.plot_right_clicked.emit()

    assert save_path.exists()

    view.close()
    if QApplication.instance() is app:
        app.processEvents()
