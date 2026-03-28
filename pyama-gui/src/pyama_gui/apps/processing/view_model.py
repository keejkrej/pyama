"""View-model for the processing tab."""

import logging
from pathlib import Path

import yaml
from PySide6.QtCore import QObject, Signal

from pyama.apps.processing.extract import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama.apps.processing.merge import (
    normalize_samples,
)
from pyama.io.microscopy import inspect_microscopy_file
from pyama.io.samples import read_samples_yaml
from pyama.tasks import (
    MergeTaskRequest,
    ProcessingTaskRequest,
    TaskStatus,
    submit_merge,
    submit_processing,
)
from pyama.types import (
    Channels,
    MergeSample,
    MergeSamplePayload,
    MicroscopyMetadata,
    ProcessingConfig,
    ProcessingParams,
)
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types.processing import ProcessingViewState

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

            metadata = inspect_microscopy_file(self._path)
            if self.cancelled:
                self.emit_failure("Loading cancelled")
                return
            self.emit_success(metadata)
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Microscopy loading failed for %s", self._path)
            self.emit_failure(str(exc))


class WorkflowWorker(TaskWorker):
    """Run the processing workflow in the background."""

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        config: ProcessingConfig,
        output_dir: Path,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._config = config
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Workflow cancelled")
                return
            record = submit_processing(
                ProcessingTaskRequest(
                    metadata=self._metadata,
                    config=self._config,
                    output_dir=self._output_dir,
                )
            )
            snapshot = self.wait_for_task(
                record,
                progress_handler=lambda progress: self.forward_progress(
                    progress.percent or 0,
                    progress.message,
                ),
            )
            if snapshot.status != TaskStatus.COMPLETED:
                self.emit_failure(snapshot.error_message or "Workflow failed")
                return
            if not bool((snapshot.result or {}).get("success", False)):
                self.emit_failure("Workflow reported failure")
                return

            self.emit_success(message=f"Results saved to {self._output_dir}")
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Workflow execution failed")
            self.emit_failure(f"Workflow error: {exc}")


class MergeWorker(TaskWorker):
    """Run sample merge in the background."""

    def __init__(self, samples: list[MergeSample], run_dir: Path) -> None:
        super().__init__()
        self._samples = samples
        self._run_dir = run_dir

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Merge cancelled")
                return
            record = submit_merge(
                MergeTaskRequest(
                    samples=self._samples,
                    input_dir=self._run_dir,
                    output_dir=self._run_dir / "traces_merged",
                )
            )
            snapshot = self.wait_for_task(
                record,
                progress_handler=lambda progress: self.forward_progress(
                    progress.percent or 0,
                    progress.message,
                ),
            )
            if snapshot.status != TaskStatus.COMPLETED:
                self.emit_failure(snapshot.error_message or "Merge failed")
                return
            message = str((snapshot.result or {}).get("message", ""))
            self.emit_success(message=message)
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Merge failed")
            self.emit_failure(str(exc))


class ProcessingViewModel(QObject):
    """Tab-level state and commands for processing."""

    state_changed = Signal()
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
        self._samples: list[MergeSample] = []
        self._merge_running = False
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._merge_runner: WorkerHandle | None = None
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self.app_view_model.microscopy_changed.connect(self._on_microscopy_changed)
        if self.app_view_model.microscopy_path is not None:
            self._on_microscopy_changed(self.app_view_model.microscopy_path)

    @property
    def state(self) -> ProcessingViewState:
        fl_rows: list[tuple[str, int, str]] = []
        label_by_channel = {
            channel_id: label
            for label, channel_id in self._fluorescence_channel_options
        }
        for channel_id, features in sorted(self._fl_features.items()):
            for feature_name in features:
                fl_rows.append(
                    (
                        label_by_channel.get(channel_id, str(channel_id)),
                        channel_id,
                        feature_name,
                    )
                )
        sample_rows = [
            {
                "name": sample.name,
                "positions": ", ".join(str(position) for position in sample.positions),
            }
            for sample in self._samples
        ]
        return ProcessingViewState(
            microscopy_path_label=str(self._microscopy_path)
            if self._microscopy_path
            else "",
            phase_channel_options=list(self._phase_channel_options),
            fluorescence_channel_options=list(self._fluorescence_channel_options),
            available_pc_features=list(self._available_pc_features),
            available_fl_features=list(self._available_fl_features),
            selected_phase_channel=self._phase_channel,
            fluorescence_feature_rows=fl_rows,
            parameter_values={
                "position_start": {"value": self._fov_start},
                "position_end": {"value": self._fov_end},
                "n_workers": {"value": self._n_workers},
                "background_weight": {"value": self._background_weight},
            },
            workflow_running=self._workflow_running,
            workflow_progress=self._workflow_progress,
            workflow_message=self._workflow_message,
            samples=sample_rows,
            merge_running=self._merge_running,
        )

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
    def parameter_defaults(self) -> dict[str, dict[str, object]]:
        return {
            "position_start": {"value": self._fov_start},
            "position_end": {"value": self._fov_end},
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
    def samples(self) -> list[dict[str, object]]:
        return [
            {"name": sample.name, "positions": list(sample.positions)}
            for sample in self._samples
        ]

    @property
    def merge_running(self) -> bool:
        return self._merge_running

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self.state_changed.emit()

    def _on_microscopy_changed(self, path: Path | None) -> None:
        if self._microscopy_path == path and (
            path is None or self._metadata is not None
        ):
            return
        self._reset_microscopy_state(keep_samples=True)
        self._microscopy_path = path
        self.metadata_changed.emit()
        self.state_changed.emit()
        if path is None:
            return

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
        self._cancel_active_workers()

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
        self.state_changed.emit()

    def _cancel_active_workers(self) -> None:
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
        self.state_changed.emit()

    def add_fluorescence_feature(
        self, *, channel: int | None, feature_name: str
    ) -> None:
        if channel is None or not feature_name:
            return
        features = self._fl_features.setdefault(int(channel), [])
        if feature_name in features:
            return
        features.append(feature_name)
        self.state_changed.emit()

    def remove_fluorescence_features(self, rows: list[tuple[int, str]]) -> None:
        if not rows:
            return
        changed = False
        for channel_id, feature_name in rows:
            features = self._fl_features.get(int(channel_id))
            if not features or feature_name not in features:
                continue
            features.remove(feature_name)
            changed = True
            if not features:
                self._fl_features.pop(int(channel_id), None)
        if changed:
            self.state_changed.emit()

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
        self.state_changed.emit()

    def set_workflow_parameters_from_raw(self, values: dict[str, str]) -> None:
        self.set_workflow_parameters(
            fov_start=self._coerce_int(values.get("position_start"), 0),
            fov_end=self._coerce_int(values.get("position_end"), -1),
            n_workers=self._coerce_int(values.get("n_workers"), 2),
            background_weight=self._coerce_float(values.get("background_weight"), 1.0),
        )

    def run_workflow(self) -> None:
        if self._workflow_running:
            return
        if self._microscopy_path is None:
            self.app_view_model.set_status_message(
                "Select a microscopy file from the Welcome tab first."
            )
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

        if self._phase_channel is None:
            self.app_view_model.set_status_message("Select a phase channel first.")
            return

        config = ProcessingConfig(
            channels=Channels(
                pc={self._phase_channel: list(self._pc_features)},
                fl={
                    channel: list(features)
                    for channel, features in sorted(self._fl_features.items())
                },
            ),
            params=ProcessingParams(
                positions=f"{self._fov_start}:{self._fov_end + 1}",
                n_workers=self._n_workers,
                background_weight=self._background_weight,
            ),
        )

        worker = WorkflowWorker(
            metadata=self._metadata,
            config=config,
            output_dir=self._workspace_dir,
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
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message(self._workflow_message)

    def cancel_workflow(self) -> None:
        if self._workflow_runner is not None:
            self._workflow_runner.cancel()

    def set_samples(self, samples: list[MergeSample]) -> None:
        self._samples = list(samples)
        self.samples_changed.emit()
        self.state_changed.emit()

    def set_samples_from_rows(self, rows: list[dict[str, str]]) -> list[MergeSample]:
        samples = self._validate_sample_rows(rows)
        self.set_samples(samples)
        return samples

    def request_load_samples(self) -> None:
        if self.app_view_model.dialog_service is None:
            raise RuntimeError("No dialog service configured.")
        path = self.app_view_model.dialog_service.select_open_file(
            "Open sample.yaml",
            str(self._workspace_dir or Path.cwd()),
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if path is not None:
            self.load_samples(path)

    def request_save_samples(self, rows: list[dict[str, str]]) -> None:
        samples = self._validate_sample_rows(rows)
        if self.app_view_model.dialog_service is None:
            raise RuntimeError("No dialog service configured.")
        path = self.app_view_model.dialog_service.select_save_file(
            "Save sample.yaml",
            str((self._workspace_dir or Path.cwd()) / "sample.yaml"),
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if path is not None:
            self.save_samples(path, samples)

    def load_samples(self, path: Path) -> None:
        try:
            data = read_samples_yaml(path)
            self._samples = normalize_samples(data["samples"])
            self.samples_changed.emit()
            self.state_changed.emit()
            self.app_view_model.set_status_message(f"Samples loaded from {path}")
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self.app_view_model.set_status_message(
                f"Failed to load samples from {path}: {exc}"
            )

    def save_samples(self, path: Path, samples: list[MergeSample]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    {"samples": [sample.to_payload() for sample in samples]},
                    handle,
                    sort_keys=False,
                )
            self._samples = list(samples)
            self.samples_changed.emit()
            self.state_changed.emit()
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
        worker.progress_value.connect(self._on_merge_progress)
        worker.finished.connect(self._on_merge_finished)
        self._merge_runner = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_merge_runner,
        )
        self._merge_running = True
        self.merge_state_changed.emit()
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Merging ROI traces...")

    def _validate_parameters(self) -> bool:
        if self._metadata is None:
            return False

        n_positions = getattr(self._metadata, "n_positions", 0)
        effective_position_end = (
            n_positions - 1 if self._fov_end == -1 else self._fov_end
        )
        if self._fov_start < 0:
            return False
        if effective_position_end < self._fov_start:
            return False
        if effective_position_end >= n_positions:
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
        if metadata.n_positions > 0:
            self._fov_start = 0
            self._fov_end = metadata.n_positions - 1
        self.metadata_changed.emit()
        self.state_changed.emit()
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
        self.state_changed.emit()
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def _on_workflow_finished(
        self, success: bool, _result: object, message: str
    ) -> None:
        self._workflow_running = False
        self._workflow_message = message
        self.workflow_state_changed.emit()
        self.state_changed.emit()
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
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if success:
            self.app_view_model.set_status_message(message)
        else:
            self.app_view_model.set_status_message(f"Merge failed: {message}")

    def _on_merge_progress(self, percent: int, message: str) -> None:
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def _clear_merge_runner(self) -> None:
        self._merge_runner = None

    @staticmethod
    def _coerce_int(value: str | None, default: int) -> int:
        try:
            return int(value) if value not in {None, ""} else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(value: str | None, default: float) -> float:
        try:
            return float(value) if value not in {None, ""} else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _validate_sample_rows(rows: list[dict[str, str]]) -> list[MergeSample]:
        payloads: list[MergeSamplePayload] = []
        for row in rows:
            payloads.append(
                {
                    "name": str(row.get("name", "")).strip(),
                    "positions": str(row.get("positions", "")).strip(),
                }
            )
        return normalize_samples(payloads)
