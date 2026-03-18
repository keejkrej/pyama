"""View-model for the visualization tab."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from pyama.tasks import scan_processing_results
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task

logger = logging.getLogger(__name__)


class ProjectLoaderWorker(TaskWorker):
    """Load workspace visualization metadata in the background."""

    def __init__(self, project_path: Path) -> None:
        super().__init__()
        self._project_path = project_path

    def run(self) -> None:
        try:
            project_results = scan_processing_results(self._project_path)
            self.emit_success(project_results.to_dict())
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Failed to load project")
            self.emit_failure(str(exc))


class VisualizationViewModel(QObject):
    """Tab-level state and commands for visualization."""

    state_changed = Signal()
    visualization_requested = Signal(dict, int, list)

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._workspace_dir = app_view_model.workspace_dir
        self._project_data: dict | None = None
        self._available_channels: list[str] = []
        self._min_fov = 0
        self._max_fov = 0
        self._details_text = "Workspace: Not set"
        self._running = False
        self._worker_handle: WorkerHandle | None = None
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self._sync_workspace_state()

    @property
    def workspace_dir(self) -> Path | None:
        return self._workspace_dir

    @property
    def project_data(self) -> dict | None:
        return self._project_data

    @property
    def available_channels(self) -> list[str]:
        return list(self._available_channels)

    @property
    def min_fov(self) -> int:
        return self._min_fov

    @property
    def max_fov(self) -> int:
        return self._max_fov

    @property
    def details_text(self) -> str:
        return self._details_text

    @property
    def running(self) -> bool:
        return self._running

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self._sync_workspace_state()
        if path is not None:
            self.load_workspace()

    def _sync_workspace_state(self) -> None:
        self._project_data = None
        self._available_channels = []
        self._min_fov = 0
        self._max_fov = 0
        if self._workspace_dir is None:
            self._details_text = "Workspace: Not set"
        else:
            self._details_text = f"Workspace: {self._workspace_dir}"
        self.state_changed.emit()

    def load_workspace(self) -> None:
        if self._running:
            return
        if self._workspace_dir is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return

        worker = ProjectLoaderWorker(self._workspace_dir)
        worker.finished.connect(self._on_project_loaded)
        self._worker_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_worker_handle,
        )
        self._running = True
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Loading project data...")

    def start_visualization(self, fov_id: int, selected_channels: list[str]) -> None:
        if not self._project_data:
            self.app_view_model.set_status_message(
                "No project loaded. Please load a project first."
            )
            return
        if not selected_channels:
            self.app_view_model.set_status_message(
                "No channels selected for visualization."
            )
            return
        self.visualization_requested.emit(
            self._project_data, fov_id, list(selected_channels)
        )

    def _on_project_loaded(self, success: bool, result: object, message: str) -> None:
        self._running = False
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if not success:
            self.app_view_model.set_status_message(self._format_project_error(message))
            return

        project_data = dict(result)
        self._project_data = project_data
        self._available_channels = self._extract_available_channels(project_data)
        fov_keys = list(project_data.get("fov_data", {}).keys())
        self._min_fov, self._max_fov = (
            (min(fov_keys), max(fov_keys)) if fov_keys else (0, 0)
        )
        self._details_text = self._format_project_details(project_data)
        self.state_changed.emit()
        n_fov = project_data.get("n_fov", 0)
        project_path = project_data.get("project_path", "unknown folder")
        self.app_view_model.set_status_message(
            f"{n_fov} FOVs loaded from {project_path}"
        )

    def _clear_worker_handle(self) -> None:
        self._worker_handle = None

    @staticmethod
    def _extract_available_channels(project_data: dict) -> list[str]:
        if not project_data.get("fov_data"):
            return []
        first_fov = next(iter(project_data["fov_data"].values()))
        channels = [key for key in first_fov.keys() if not key.startswith("traces")]
        return sorted(channels)

    @staticmethod
    def _format_project_details(project_data: dict) -> str:
        details = [
            f"Project Path: {project_data.get('project_path', 'Unknown')}",
            f"FOVs: {project_data.get('n_fov', 0)}",
        ]
        if time_units := project_data.get("time_units", "min"):
            details.append(f"Time Units: {time_units}")
        if project_data.get("fov_data"):
            first_fov = next(iter(project_data["fov_data"].values()))
            details.append("Available Data:")
            details.extend([f"   • {data_type}" for data_type in first_fov.keys()])
        return "\n".join(details)

    @staticmethod
    def _format_project_error(message: str) -> str:
        if "No FOV directories found" in message:
            return (
                "No data found in the workspace. Ensure it contains FOV subdirectories."
            )
        return message
