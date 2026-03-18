"""View-model for the processing tab."""

import logging
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal

from pyama.tasks import (
    WorkflowStatusEvent,
    WorkflowTaskManager,
    ensure_context,
    list_fluorescence_features,
    list_phase_features,
    load_microscopy_file,
    read_samples_yaml,
    run_merge,
)
from pyama.types import (
    ChannelSelection,
    Channels,
    MicroscopyMetadata,
    ProcessingContext,
)
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task

logger = logging.getLogger(__name__)


class MicroscopyLoaderWorker(TaskWorker):
    """Load microscopy metadata in the background."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Loading cancelled")
                return

            reader, metadata = load_microscopy_file(self._path)
            try:
                if self.cancelled:
                    self.emit_failure("Loading cancelled")
                    return
                self.emit_success(metadata)
            finally:
                try:
                    reader.close()
                except Exception:
                    logger.debug(
                        "Failed to close microscopy reader after metadata load for %s",
                        self._path,
                        exc_info=True,
                    )
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Microscopy loading failed for %s", self._path)
            self.emit_failure(str(exc))


class WorkflowWorker(TaskWorker):
    """Run the processing workflow in the background."""

    progress_value = Signal(int, str)

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        fov_start: int,
        fov_end: int,
        n_workers: int,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._context = ensure_context(context)
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._n_workers = n_workers
        self._task_manager = WorkflowTaskManager()

    def run(self) -> None:
        try:
            if self._task_manager.cancel_event.is_set():
                self.emit_failure("Workflow cancelled")
                return

            def _on_progress(event: object) -> None:
                if isinstance(event, WorkflowStatusEvent):
                    self.progress_value.emit(event.progress_percent, event.message)

            success = self._task_manager.run(
                metadata=self._metadata,
                context=self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                n_workers=self._n_workers,
                progress_reporter=_on_progress,
            )
            if self._task_manager.cancel_event.is_set() or self.cancelled:
                self.emit_failure("Workflow cancelled")
                return
            if not success:
                self.emit_failure("Workflow reported failure")
                return

            output_dir = self._context.output_dir or "output directory"
            self.emit_success(message=f"Results saved to {output_dir}")
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Workflow execution failed")
            self.emit_failure(f"Workflow error: {exc}")

    def cancel(self) -> None:
        super().cancel()
        self._task_manager.cancel()


class MergeWorker(TaskWorker):
    """Run sample merge in the background."""

    def __init__(
        self, samples: list[dict[str, Any]], processing_results_dir: Path
    ) -> None:
        super().__init__()
        self._samples = samples
        self._processing_results_dir = processing_results_dir

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Merge cancelled")
                return
            message = run_merge(self._samples, self._processing_results_dir)
            self.emit_success(message=message)
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Merge failed")
            self.emit_failure(str(exc))


class ProcessingViewModel(QObject):
    """Tab-level state and commands for processing."""

    metadata_changed = Signal()
    workflow_state_changed = Signal()
    samples_changed = Signal()
    merge_state_changed = Signal()

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._workspace_dir = app_view_model.workspace_dir
        self._microscopy_path: Path | None = None
        self._metadata: MicroscopyMetadata | None = None
        self._phase_channel_options: list[tuple[str, int]] = []
        self._fluorescence_channel_options: list[tuple[str, int]] = []
        self._available_pc_features = list_phase_features()
        self._available_fl_features = list_fluorescence_features()
        self._phase_channel: int | None = None
        self._pc_features: list[str] = []
        self._fl_features: dict[int, list[str]] = {}
        self._fov_start = 0
        self._fov_end = -1
        self._n_workers = 2
        self._background_weight = 1.0
        self._workflow_running = False
        self._workflow_progress = 0
        self._workflow_message = ""
        self._samples: list[dict[str, Any]] = []
        self._merge_running = False
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._merge_runner: WorkerHandle | None = None
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)

    @property
    def microscopy_path(self) -> Path | None:
        return self._microscopy_path

    @property
    def metadata(self) -> MicroscopyMetadata | None:
        return self._metadata

    @property
    def phase_channel_options(self) -> list[tuple[str, int]]:
        return list(self._phase_channel_options)

    @property
    def fluorescence_channel_options(self) -> list[tuple[str, int]]:
        return list(self._fluorescence_channel_options)

    @property
    def available_pc_features(self) -> list[str]:
        return list(self._available_pc_features)

    @property
    def available_fl_features(self) -> list[str]:
        return list(self._available_fl_features)

    @property
    def parameter_defaults(self) -> dict[str, dict[str, Any]]:
        return {
            "fov_start": {"value": self._fov_start},
            "fov_end": {"value": self._fov_end},
            "n_workers": {"value": self._n_workers},
            "background_weight": {"value": self._background_weight},
        }

    @property
    def workflow_running(self) -> bool:
        return self._workflow_running

    @property
    def workflow_progress(self) -> int:
        return self._workflow_progress

    @property
    def workflow_message(self) -> str:
        return self._workflow_message

    @property
    def samples(self) -> list[dict[str, Any]]:
        return [dict(sample) for sample in self._samples]

    @property
    def merge_running(self) -> bool:
        return self._merge_running

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path

    def select_microscopy(self, path: Path) -> None:
        self._reset_microscopy_state(keep_samples=True)
        self._microscopy_path = path
        self.metadata_changed.emit()
        self.app_view_model.set_status_message("Loading microscopy file...")
        self.app_view_model.begin_busy()

        worker = MicroscopyLoaderWorker(path)
        worker.finished.connect(self._on_microscopy_finished)
        self._microscopy_loader = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_microscopy_loader,
        )

    def _reset_microscopy_state(self, *, keep_samples: bool) -> None:
        if self._microscopy_loader:
            self._microscopy_loader.cancel()
            self._microscopy_loader = None
            self.app_view_model.end_busy()
        if self._workflow_runner:
            self._workflow_runner.cancel()
            self._workflow_runner = None
            if self._workflow_running:
                self.app_view_model.end_busy()
        if self._merge_runner:
            self._merge_runner.cancel()
            self._merge_runner = None
            if self._merge_running:
                self.app_view_model.end_busy()

        self._metadata = None
        self._microscopy_path = None
        self._phase_channel_options = []
        self._fluorescence_channel_options = []
        self._phase_channel = None
        self._pc_features = []
        self._fl_features = {}
        self._fov_start = 0
        self._fov_end = -1
        self._n_workers = 2
        self._background_weight = 1.0
        self._workflow_running = False
        self._workflow_progress = 0
        self._workflow_message = ""
        self._merge_running = False
        if not keep_samples:
            self._samples = []
            self.samples_changed.emit()
        self.workflow_state_changed.emit()
        self.merge_state_changed.emit()
        self.metadata_changed.emit()

    def set_channel_selection(
        self,
        *,
        phase_channel: int | None,
        pc_features: list[str],
        fl_features: dict[int, list[str]],
    ) -> None:
        self._phase_channel = phase_channel
        self._pc_features = list(pc_features)
        self._fl_features = {
            int(channel): list(features) for channel, features in fl_features.items()
        }

    def set_workflow_parameters(
        self,
        *,
        fov_start: int,
        fov_end: int,
        n_workers: int,
        background_weight: float,
    ) -> None:
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._n_workers = n_workers
        self._background_weight = background_weight
        self.workflow_state_changed.emit()

    def run_workflow(self) -> None:
        if self._workflow_running:
            return
        if self._microscopy_path is None:
            self.app_view_model.set_status_message("Select a microscopy file first.")
            return
        if self._workspace_dir is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return
        if self._metadata is None:
            self.app_view_model.set_status_message(
                "Microscopy metadata is still loading."
            )
            return
        if (
            self._phase_channel is None
            and not self._fl_features
            and not self._pc_features
        ):
            self.app_view_model.set_status_message(
                "Select at least one channel feature."
            )
            return
        if self._pc_features and self._phase_channel is None:
            self.app_view_model.set_status_message(
                "Select a phase channel for phase features."
            )
            return
        if not self._validate_parameters():
            self.app_view_model.set_status_message("Processing parameters are invalid.")
            return

        pc_selection = (
            ChannelSelection(
                channel=self._phase_channel, features=list(self._pc_features)
            )
            if self._phase_channel is not None
            else None
        )
        fl_selections = [
            ChannelSelection(channel=channel, features=list(features))
            for channel, features in sorted(self._fl_features.items())
        ]
        context = ProcessingContext(
            output_dir=self._workspace_dir,
            channels=Channels(pc=pc_selection, fl=fl_selections),
            params={"background_weight": self._background_weight},
            time_units="",
        )

        worker = WorkflowWorker(
            metadata=self._metadata,
            context=context,
            fov_start=self._fov_start,
            fov_end=self._fov_end,
            n_workers=self._n_workers,
        )
        worker.progress_value.connect(self._on_workflow_progress)
        worker.finished.connect(self._on_workflow_finished)
        self._workflow_runner = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_runner,
        )

        self._workflow_running = True
        self._workflow_progress = 0
        self._workflow_message = "Processing workflow started..."
        self.workflow_state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message(self._workflow_message)

    def cancel_workflow(self) -> None:
        if self._workflow_runner is not None:
            self._workflow_runner.cancel()

    def set_samples(self, samples: list[dict[str, Any]]) -> None:
        self._samples = [dict(sample) for sample in samples]
        self.samples_changed.emit()

    def load_samples(self, path: Path) -> None:
        try:
            data = read_samples_yaml(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be a list.")
            self._samples = [dict(sample) for sample in samples]
            self.samples_changed.emit()
            self.app_view_model.set_status_message(f"Samples loaded from {path}")
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self.app_view_model.set_status_message(
                f"Failed to load samples from {path}: {exc}"
            )

    def save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump({"samples": samples}, handle, sort_keys=False)
            self._samples = [dict(sample) for sample in samples]
            self.samples_changed.emit()
            self.app_view_model.set_status_message(f"Samples saved to {path}")
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            self.app_view_model.set_status_message(
                f"Failed to save samples to {path}: {exc}"
            )

    def run_merge(self) -> None:
        if self._merge_running:
            return
        if self._workspace_dir is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return
        if not self._samples:
            self.app_view_model.set_status_message(
                "Add or load sample assignments first."
            )
            return

        worker = MergeWorker(self._samples, self._workspace_dir.expanduser())
        worker.finished.connect(self._on_merge_finished)
        self._merge_runner = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_merge_runner,
        )
        self._merge_running = True
        self.merge_state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Merging processing results...")

    def _validate_parameters(self) -> bool:
        if self._metadata is None:
            return False

        n_fovs = getattr(self._metadata, "n_fovs", 0)
        effective_fov_end = n_fovs - 1 if self._fov_end == -1 else self._fov_end
        if self._fov_start < 0:
            return False
        if effective_fov_end < self._fov_start:
            return False
        if effective_fov_end >= n_fovs:
            return False
        if self._n_workers <= 0:
            return False
        return True

    def _on_microscopy_finished(
        self,
        success: bool,
        metadata: MicroscopyMetadata | None,
        message: str,
    ) -> None:
        self.app_view_model.end_busy()
        if not success or metadata is None:
            self.app_view_model.set_status_message(
                message or "Failed to load microscopy metadata."
            )
            return

        self._metadata = metadata
        self._phase_channel_options = []
        self._fluorescence_channel_options = []
        for index, channel_name in enumerate(metadata.channel_names):
            label = f"{index}: {channel_name}" if channel_name else str(index)
            self._phase_channel_options.append((label, index))
            self._fluorescence_channel_options.append((label, index))
        if metadata.n_fovs > 0:
            self._fov_start = 0
            self._fov_end = metadata.n_fovs - 1
        self.metadata_changed.emit()
        filename = (
            self._microscopy_path.name if self._microscopy_path else "Microscopy file"
        )
        self.app_view_model.set_status_message(f"{filename} loaded successfully")

    def _clear_microscopy_loader(self) -> None:
        self._microscopy_loader = None

    def _on_workflow_progress(self, percent: int, message: str) -> None:
        self._workflow_progress = percent
        self._workflow_message = message
        self.workflow_state_changed.emit()
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def _on_workflow_finished(
        self, success: bool, _result: object, message: str
    ) -> None:
        self._workflow_running = False
        self._workflow_message = message
        self.workflow_state_changed.emit()
        self.app_view_model.end_busy()
        if success:
            self.app_view_model.set_status_message(message)
        else:
            self.app_view_model.set_status_message(f"Processing failed: {message}")

    def _clear_workflow_runner(self) -> None:
        self._workflow_runner = None

    def _on_merge_finished(self, success: bool, _result: object, message: str) -> None:
        self._merge_running = False
        self.merge_state_changed.emit()
        self.app_view_model.end_busy()
        if success:
            self.app_view_model.set_status_message(message)
        else:
            self.app_view_model.set_status_message(f"Merge failed: {message}")

    def _clear_merge_runner(self) -> None:
        self._merge_runner = None
