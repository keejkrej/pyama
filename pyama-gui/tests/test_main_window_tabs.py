import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QPushButton, QSlider

from pyama.io.zarr import open_raw_zarr, open_rois_zarr
from pyama.types import MicroscopyMetadata
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.bboxes.view import BBoxesView
from pyama_gui.apps.bboxes.view_model import BBoxesViewModel
from pyama_gui.apps.modeling.view_model import ModelingViewModel
from pyama_gui.apps.welcome.view import WelcomeView
from pyama_gui.components import PyQtGraphImageView, ViewCanvas
from pyama_gui.main_window import MainWindow
from pyama_gui.services import FileDialogService, PathRevealService
from pyama_gui.apps.modeling.view import ModelingView
from pyama_gui.apps.processing.view import ProcessingView
from pyama_gui.apps.processing.view_model import ProcessingViewModel
from pyama_gui.apps.statistics.view import StatisticsView
from pyama_gui.apps.statistics.view_model import StatisticsViewModel
from pyama_gui.apps.visualization.view import VisualizationView
from pyama_gui.apps.visualization.view_model import VisualizationViewModel


class _StubAlignCanvasBackendServer:
    def __init__(self) -> None:
        self.url = "ws://127.0.0.1:0"

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None


def _stub_align_canvas_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pyama_gui.apps.bboxes.view_model.AlignCanvasBackendServer",
        _StubAlignCanvasBackendServer,
    )


def _write_analysis_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(rows).to_csv(path, index=False)


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


class StubPathRevealService(PathRevealService):
    def __init__(self) -> None:
        self.revealed_paths: list[Path] = []

    def reveal_path(self, path: Path) -> None:
        self.revealed_paths.append(path)


def test_main_window_has_consolidated_tabs() -> None:
    app = QApplication.instance() or QApplication([])

    window = MainWindow()

    assert window.status_bar.paths_button.text() == "Info"
    assert window.status_bar.path_entry_text("Workspace") == "Not set"
    assert window.status_bar.path_entry_text("Microscopy") == "Not set"
    assert not window.menuBar().actions()
    assert [window.tabs.tabText(index) for index in range(window.tabs.count())] == [
        "Welcome",
        "Alignment",
        "Processing",
        "Statistics",
        "Modeling",
        "Visualization",
    ]
    assert isinstance(window.welcome_tab, WelcomeView)
    assert window.bboxes_tab is None
    assert window.processing_tab is None

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_main_window_loads_non_welcome_tabs_lazily(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    _stub_align_canvas_backend(monkeypatch)

    window = MainWindow()

    assert isinstance(window.welcome_tab, WelcomeView)
    assert window.bboxes_tab is None
    assert window.processing_tab is None
    assert window.statistics_tab is None
    assert window.modeling_tab is None
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(1)
    app.processEvents()
    assert isinstance(window.bboxes_tab, BBoxesView)
    assert window.processing_tab is None
    assert window.statistics_tab is None
    assert window.modeling_tab is None

    window.tabs.setCurrentIndex(2)
    app.processEvents()
    assert isinstance(window.processing_tab, ProcessingView)
    assert window.statistics_tab is None

    window.tabs.setCurrentIndex(3)
    app.processEvents()
    assert isinstance(window.statistics_tab, StatisticsView)
    assert window.modeling_tab is None

    window.tabs.setCurrentIndex(4)
    app.processEvents()
    assert isinstance(window.modeling_tab, ModelingView)
    assert window.visualization_tab is None

    window.tabs.setCurrentIndex(5)
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
    assert window.status_bar.path_entry_text("Workspace") == workspace.stem

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_welcome_tab_buttons_update_app_state_and_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    workspace = Path("/tmp/welcome-tab-workspace")
    microscopy = Path("/tmp/welcome-tab-input.nd2")

    _stub_align_canvas_backend(monkeypatch)
    window = MainWindow(
        dialog_service=StubDialogService(directory=workspace, open_file=microscopy)
    )
    assert isinstance(window.welcome_tab, WelcomeView)

    window.welcome_tab.workspace_button.click()
    window.welcome_tab.microscopy_button.click()

    assert window.app_view_model.microscopy_path == microscopy
    assert window.app_view_model.workspace_dir == workspace
    assert window.status_bar.path_entry_text("Workspace") == workspace.stem
    assert window.status_bar.path_entry_text("Microscopy") == microscopy.stem

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_status_bar_path_menu_reveals_current_paths() -> None:
    app = QApplication.instance() or QApplication([])
    reveal_service = StubPathRevealService()
    workspace = Path("/tmp/status-bar-workspace")
    microscopy = Path("/tmp/status-bar-input.nd2")

    window = MainWindow(path_reveal_service=reveal_service)
    window.app_view_model.set_workspace_dir(workspace)
    window.app_view_model.set_microscopy_path(microscopy)

    window.status_bar.paths_button.click()
    app.processEvents()
    assert window.status_bar.paths_menu.isVisible()

    window.status_bar.paths_menu.entry_action("Workspace").trigger()
    window.status_bar.paths_button.click()
    app.processEvents()
    window.status_bar.paths_menu.entry_action("Microscopy").trigger()

    assert reveal_service.revealed_paths == [workspace, microscopy]

    window.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_tab_loads_existing_workspace_when_lazy_created(
    tmp_path: Path,
) -> None:
    app = QApplication.instance() or QApplication([])
    workspace = tmp_path / "workspace"
    traces_merged = workspace / "traces_merged"
    _write_analysis_csv(
        traces_merged / "intensity_total_c1" / "sample_a.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        traces_merged / "area_c0" / "sample_a.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )

    window = MainWindow()
    window.app_view_model.set_workspace_dir(workspace)
    window.tabs.setCurrentIndex(3)
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
    window.tabs.setCurrentIndex(5)
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
    microscopy = Path("/tmp/example-microscopy.nd2")

    assert app_view_model.workspace_dir is None
    assert app_view_model.microscopy_path is None
    assert app_view_model.busy is False
    assert app_view_model.status_message == "Ready"

    app_view_model.set_workspace_dir(workspace)
    app_view_model.set_microscopy_path(microscopy)
    app_view_model.set_status_message("Loading")
    app_view_model.begin_busy()
    app_view_model.begin_busy()
    app_view_model.end_busy()

    assert app_view_model.workspace_dir == workspace
    assert app_view_model.microscopy_path == microscopy
    assert app_view_model.status_message == "Loading"
    assert app_view_model.busy is True

    app_view_model.end_busy()
    assert app_view_model.busy is False


def test_processing_view_model_reports_missing_inputs() -> None:
    app_view_model = AppViewModel(dialog_service=StubDialogService())
    view_model = ProcessingViewModel(app_view_model)

    view_model.run_workflow()

    assert (
        app_view_model.status_message
        == "Select a microscopy file from the Welcome tab first."
    )


def test_app_view_model_selects_and_clears_microscopy() -> None:
    workspace = Path("/tmp/workspace")
    microscopy = Path("/tmp/input.nd2")
    app_view_model = AppViewModel(
        dialog_service=StubDialogService(directory=workspace, open_file=microscopy)
    )

    app_view_model.set_workspace_dir(workspace)
    app_view_model.select_microscopy()

    assert app_view_model.microscopy_path == microscopy
    assert app_view_model.status_message == f"Microscopy file set to {microscopy}"

    app_view_model.clear_microscopy()

    assert app_view_model.microscopy_path is None
    assert app_view_model.status_message == "Microscopy file cleared"


def test_bboxes_view_model_saves_workspace_bbox_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    microscopy = tmp_path / "input.nd2"
    microscopy.write_text("stub", encoding="utf-8")
    _stub_align_canvas_backend(monkeypatch)

    monkeypatch.setattr(
        "pyama_gui.apps.bboxes.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )
    monkeypatch.setattr(
        "pyama_gui.apps.bboxes.view_model.inspect_microscopy_file",
        lambda path: MicroscopyMetadata(
            file_path=path,
            base_name=path.stem,
            file_type="nd2",
            height=4,
            width=5,
            n_frames=3,
            channel_names=("PC", "GFP"),
            dtype="uint16",
            timepoints=(0.0, 5.0, 10.0),
            position_list=(0, 1),
            z_slices=(0, 1),
        ),
    )

    app_view_model = AppViewModel()
    app_view_model.set_workspace_dir(tmp_path / "workspace")
    view_model = BBoxesViewModel(app_view_model)
    app_view_model.set_microscopy_path(microscopy)

    view_model.handle_canvas_frame_loaded(
        {
            "width": 5,
            "height": 4,
            "contrastDomain": {"min": 0, "max": 65535},
            "suggestedContrast": {"min": 1, "max": 19},
            "appliedContrast": {"min": 1, "max": 19},
        }
    )
    view_model.set_grid_patch({"enabled": True, "cellWidth": 2.0, "cellHeight": 2.0})
    view_model.save_current_bboxes()

    saved_path = tmp_path / "workspace" / "bbox" / "Pos0.csv"
    assert saved_path.exists()
    assert saved_path.read_text(encoding="utf-8").startswith("crop,x,y,w,h\n")
    view_model.shutdown()


def test_bboxes_view_model_exposes_z_contrast_and_disable_edge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    microscopy = tmp_path / "input.nd2"
    microscopy.write_text("stub", encoding="utf-8")
    _stub_align_canvas_backend(monkeypatch)

    monkeypatch.setattr(
        "pyama_gui.apps.bboxes.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )
    monkeypatch.setattr(
        "pyama_gui.apps.bboxes.view_model.inspect_microscopy_file",
        lambda path: MicroscopyMetadata(
            file_path=path,
            base_name=path.stem,
            file_type="nd2",
            height=4,
            width=5,
            n_frames=3,
            channel_names=("PC", "GFP"),
            dtype="uint16",
            timepoints=(0.0, 5.0, 10.0),
            position_list=(0, 1),
            z_slices=(0, 1),
        ),
    )

    app_view_model = AppViewModel()
    view_model = BBoxesViewModel(app_view_model)
    app_view_model.set_microscopy_path(microscopy)

    state = view_model.state
    assert state.z_options == [("0", 0), ("1", 1)]
    assert state.selected_z == 0
    assert state.time_values == ["0", "5", "10"]
    assert state.loading_frame is True

    view_model.handle_canvas_frame_loaded(
        {
            "width": 5,
            "height": 4,
            "contrastDomain": {"min": 0, "max": 1023},
            "suggestedContrast": {"min": 12, "max": 900},
            "appliedContrast": {"min": 12, "max": 900},
        }
    )
    state = view_model.state
    assert state.loading_frame is False
    assert state.can_disable_edge is True

    view_model.set_selected_z(1)
    state = view_model.state
    assert state.selected_z == 1
    assert state.loading_frame is True

    previous_min = state.contrast_min
    previous_max = state.contrast_max
    view_model.auto_contrast_current_frame()
    state = view_model.state
    assert state.loading_frame is True
    view_model.handle_canvas_frame_loaded(
        {
            "width": 5,
            "height": 4,
            "contrastDomain": {"min": 0, "max": 1023},
            "suggestedContrast": {"min": 100, "max": 750},
            "appliedContrast": {"min": 100, "max": 750},
        }
    )
    state = view_model.state
    assert (state.contrast_min, state.contrast_max) != (previous_min, previous_max)

    view_model.set_grid_patch(
        {
            "enabled": True,
            "cellWidth": 2.0,
            "cellHeight": 2.0,
            "spacingA": 2.0,
            "spacingB": 2.0,
        }
    )
    included_before = view_model.state.included_count
    view_model.disable_edge_cells()
    state = view_model.state
    assert state.excluded_count > 0
    assert state.included_count < included_before
    view_model.shutdown()


def test_bboxes_view_matches_align_panel_structure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = QApplication.instance() or QApplication([])
    _stub_align_canvas_backend(monkeypatch)

    view = BBoxesView(AppViewModel())

    group_boxes = view.findChildren(QGroupBox)
    assert len(group_boxes) == 2
    assert sorted(group.minimumWidth() for group in group_boxes) == [280, 320]

    label_texts = {label.text() for label in view.findChildren(QLabel)}
    assert {"Image", "Contrast", "Grid", "Select"} <= label_texts
    assert any(isinstance(widget, QSlider) for widget in view.findChildren(QSlider))
    assert view._disable_edge_button.text() == "Disable Edge"
    assert isinstance(view._canvas_view, ViewCanvas)

    view.close()
    if QApplication.instance() is app:
        app.processEvents()


def test_statistics_view_model_enables_area_normalization_only_for_complete_samples(
    tmp_path: Path,
) -> None:
    mixed_folder = tmp_path / "traces_merged"
    _write_analysis_csv(
        mixed_folder / "intensity_total_c1" / "sample_a.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "area_c0" / "sample_a.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        mixed_folder / "intensity_total_c1" / "sample_b.csv",
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
    _write_analysis_csv(
        complete_folder / "intensity_total_c1" / "sample_a.csv",
        [{"frame": 0, "position": 0, "roi": 0, "value": 1.0}],
    )
    _write_analysis_csv(
        complete_folder / "area_c0" / "sample_a.csv",
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


def test_visualization_view_model_excludes_non_roi_channels(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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

    assert view_model.state.available_channels == []
    assert view_model.state.current_image is None
    assert view_model.state.data_types == []
    assert view_model.state.trace_rows


def test_visualization_view_model_loads_roi_only_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace = tmp_path / "visualization_workspace"
    workspace.mkdir()
    store = open_rois_zarr(workspace / "rois.zarr", mode="a")
    store.write_roi_ids(0, np.array([7], dtype=np.int32))
    store.write_roi_bboxes(0, np.array([[1, 1, 2, 2]], dtype=np.int32))
    store.write_roi_raw_frame(
        position_id=0,
        channel_id=1,
        roi_id=7,
        frame_idx=0,
        data=np.arange(6, dtype=np.uint16).reshape(2, 3),
    )
    store.write_roi_raw_frame(
        position_id=0,
        channel_id=1,
        roi_id=7,
        frame_idx=1,
        data=np.arange(6, 12, dtype=np.uint16).reshape(2, 3),
    )
    traces_dir = workspace / "traces"
    traces_dir.mkdir()
    pd.DataFrame(
        [
            {
                "position": 0,
                "roi": 7,
                "frame": 0,
                "is_good": True,
                "x": 1.0,
                "y": 1.0,
                "w": 2.0,
                "h": 2.0,
                "intensity_total_c1": 10.0,
            },
            {
                "position": 0,
                "roi": 7,
                "frame": 1,
                "is_good": True,
                "x": 1.0,
                "y": 1.0,
                "w": 2.0,
                "h": 2.0,
                "intensity_total_c1": 11.0,
            },
        ]
    ).to_csv(traces_dir / "position_0.csv", index=False)

    monkeypatch.setattr(
        "pyama_gui.apps.visualization.view_model.run_task",
        lambda worker, **kwargs: worker.run(),
    )

    view_model = VisualizationViewModel(AppViewModel())
    view_model.app_view_model.set_workspace_dir(workspace)
    view_model.set_selected_channels(["roi_raw_ch_1"])
    view_model.start_visualization()

    assert view_model.state.current_image is not None
    assert view_model.state.current_image.shape == (2, 3)
    assert view_model.state.data_types == ["roi_raw_ch_1"]
    assert view_model.state.trace_rows
    assert view_model.state.overlays == []


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
