"""Processing tab orchestration for workflow and merge functionality."""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pyama_core.io import MicroscopyMetadata, load_microscopy_file
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.types.processing import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)
from pyama_pro.processing.input import InputPanel
from pyama_pro.processing.merge import MergePanel
from pyama_pro.processing.output import OutputPanel
from pyama_pro.utils import WorkerHandle, start_worker

logger = logging.getLogger(__name__)


class MicroscopyLoaderWorker(QObject):
    """Background worker for loading microscopy metadata."""

    finished = Signal(bool, object, str)

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished.emit(False, None, "Loading cancelled")
                return

            reader, metadata = load_microscopy_file(self._path)
            try:
                if not self._cancelled:
                    self.finished.emit(True, metadata, "")
            finally:
                try:
                    reader.close()
                except Exception:
                    logger.debug(
                        "Failed to close microscopy reader after metadata load for %s",
                        self._path,
                        exc_info=True,
                    )
        except Exception as exc:  # pragma: no cover - propagate to UI
            if not self._cancelled:
                logger.exception("Microscopy loading failed for %s", self._path)
                self.finished.emit(False, None, str(exc))


class ProcessingWorkflowWorker(QObject):
    """Background worker for running the processing workflow."""

    finished = Signal(bool, str)

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
        self._cancel_event = threading.Event()

    def run(self) -> None:
        try:
            if self._cancel_event.is_set():
                logger.info(
                    "Workflow cancelled before execution (fovs=%d-%d)",
                    self._fov_start,
                    self._fov_end,
                )
                self.finished.emit(False, "Workflow cancelled")
                return

            logger.info(
                "Workflow execution started (fovs=%d-%d, workers=%d, output_dir=%s)",
                self._fov_start,
                self._fov_end,
                self._n_workers,
                self._context.output_dir,
            )

            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                n_workers=self._n_workers,
                cancel_event=self._cancel_event,
            )

            if self._cancel_event.is_set():
                logger.info(
                    "Workflow was cancelled during execution (fovs=%d-%d)",
                    self._fov_start,
                    self._fov_end,
                )
                self.finished.emit(False, "Workflow cancelled")
                return

            if success:
                output_dir = self._context.output_dir or "output directory"
                self.finished.emit(True, f"Results saved to {output_dir}")
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")

    def cancel(self) -> None:
        logger.info(
            "Cancelling workflow execution (fovs=%d-%d, output_dir=%s)",
            self._fov_start,
            self._fov_end,
            self._context.output_dir,
        )
        self._cancel_event.set()


class ProcessingTab(QWidget):
    """Processing page orchestrator for input, output, and merge panels."""

    processing_started = Signal()
    processing_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._metadata: MicroscopyMetadata | None = None
        self._microscopy_path: Path | None = None
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._build_ui()
        self._connect_signals()
        self._initialize_workflow_state()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        self._input_panel = InputPanel(self)
        self._output_panel = OutputPanel(self)
        self._merge_panel = MergePanel(self)

        layout.addWidget(self._input_panel, 1)
        layout.addWidget(self._output_panel, 1)
        layout.addWidget(self._merge_panel, 1)

    def _connect_signals(self) -> None:
        self._input_panel.microscopy_selected.connect(self._on_microscopy_selected)
        self._output_panel.process_requested.connect(self._on_process_clicked)
        self._output_panel.cancel_requested.connect(self._on_cancel_workflow)

        self._merge_panel.merge_started.connect(self._on_merge_started)
        self._merge_panel.merge_finished.connect(self._on_merge_finished)
        self._merge_panel.samples_loading_started.connect(
            self._on_samples_loading_started
        )
        self._merge_panel.samples_loading_finished.connect(
            self._on_samples_loading_finished
        )
        self._merge_panel.samples_saving_started.connect(
            self._on_samples_saving_started
        )
        self._merge_panel.samples_saving_finished.connect(
            self._on_samples_saving_finished
        )

    def _initialize_workflow_state(self) -> None:
        logger.info(
            "Resetting workflow panel to initial state (clearing paths, features, parameters)"
        )
        if self._microscopy_loader:
            self._microscopy_loader.cancel()
            self._microscopy_loader = None
        if self._workflow_runner:
            self._workflow_runner.cancel()
            self._workflow_runner = None

        self._metadata = None
        self._microscopy_path = None
        self._input_panel.reset()
        self._output_panel.reset()

    def _update_fov_parameters(self, fov_start: int, fov_end: int) -> None:
        self._output_panel.set_parameter_defaults(
            {
                "fov_start": {"value": fov_start},
                "fov_end": {"value": fov_end},
                "n_workers": {"value": self._output_panel.n_workers},
                "background_weight": {"value": self._output_panel.background_weight},
            }
        )
        logger.debug(
            "Updated FOV parameters in UI: fov_start=%d, fov_end=%d",
            fov_start,
            fov_end,
        )

    @Slot(object)
    def _on_microscopy_selected(self, path: Path) -> None:
        self._initialize_workflow_state()
        self._microscopy_path = path
        self._input_panel.display_microscopy_path(path)
        self._load_microscopy(path)

    def _load_microscopy(self, path: Path) -> None:
        logger.info("Loading microscopy metadata from %s", path)
        self._on_microscopy_loading_started()

        worker = MicroscopyLoaderWorker(path)
        worker.finished.connect(self._on_microscopy_finished)
        self._microscopy_loader = start_worker(
            worker,
            start_method="run",
            finished_callback=self._on_loader_finished,
        )

    @Slot(bool, object, str)
    def _on_microscopy_finished(
        self,
        success: bool,
        metadata: MicroscopyMetadata | None,
        error_message: str,
    ) -> None:
        if success and metadata:
            channel_count = len(getattr(metadata, "channel_names", []))
            fov_count = getattr(metadata, "n_fovs", 0)
            logger.info(
                "Microscopy metadata loaded (channels=%d, fovs=%d)",
                channel_count,
                fov_count,
            )
            self._metadata = metadata
            self._input_panel.load_microscopy_metadata(metadata)

            if metadata.n_fovs > 0:
                self._update_fov_parameters(0, metadata.n_fovs - 1)

            filename = (
                self._microscopy_path.name if self._microscopy_path else "microscopy file"
            )
            self._on_microscopy_loading_finished(True, f"{filename} loaded successfully")
            return

        filename = (
            self._microscopy_path.name if self._microscopy_path else "microscopy file"
        )
        logger.error(
            "Failed to load microscopy metadata for %s (success=%s, error=%s)",
            filename,
            success,
            error_message or "unknown error",
        )
        self._on_microscopy_loading_finished(
            False,
            error_message or f"Failed to load {filename}",
        )

    @Slot()
    def _on_loader_finished(self) -> None:
        logger.info(
            "Microscopy loader thread finished for %s",
            self._microscopy_path or "current session",
        )
        self._microscopy_loader = None

    @Slot()
    def _on_process_clicked(self) -> None:
        logger.debug(
            "UI Click: Process workflow button (microscopy=%s, output_dir=%s)",
            self._microscopy_path,
            self._output_panel.output_dir,
        )
        self._start_workflow()

    @Slot()
    def _on_cancel_workflow(self) -> None:
        logger.debug(
            "UI Click: Cancel workflow button (workflow_running=%s)",
            bool(self._workflow_runner),
        )
        if self._workflow_runner:
            logger.info(
                "Cancelling workflow execution for %s",
                self._microscopy_path or "current session",
            )
            self._workflow_runner.cancel()
            return

        self._output_panel.set_process_enabled(True)

    def _start_workflow(self) -> None:
        phase_channel = self._input_panel.phase_channel
        fl_features = self._input_panel.fl_features
        pc_features = self._input_panel.pc_features
        output_dir = self._output_panel.output_dir

        if not self._microscopy_path:
            return
        if not output_dir:
            return
        if pc_features and phase_channel is None:
            return
        if phase_channel is None and not fl_features and not pc_features:
            return
        if not self._validate_parameters():
            return

        pc_selection = (
            ChannelSelection(channel=phase_channel, features=list(pc_features))
            if phase_channel is not None
            else None
        )
        fl_selections = [
            ChannelSelection(channel=int(channel), features=list(features))
            for channel, features in sorted(fl_features.items())
        ]

        context = ProcessingContext(
            output_dir=output_dir,
            channels=Channels(pc=pc_selection, fl=fl_selections),
            params={"background_weight": self._output_panel.background_weight},
            time_units="",
        )

        resolved_fov_end = (
            getattr(self._metadata, "n_fovs", 0) - 1
            if self._output_panel.fov_end == -1 and self._metadata
            else self._output_panel.fov_end
        )
        logger.debug("ProcessingContext built from user input: %s", context)
        logger.debug(
            "Workflow parameters: FOV range=%d-%d, n_workers=%d",
            self._output_panel.fov_start,
            resolved_fov_end,
            self._output_panel.n_workers,
        )
        logger.info(
            "Starting workflow for %s -> %s (fovs=%d-%d, workers=%d)",
            getattr(self._microscopy_path, "name", "selected file"),
            output_dir,
            self._output_panel.fov_start,
            resolved_fov_end,
            self._output_panel.n_workers,
        )

        worker = ProcessingWorkflowWorker(
            metadata=self._metadata,
            context=context,
            fov_start=self._output_panel.fov_start,
            fov_end=self._output_panel.fov_end,
            n_workers=self._output_panel.n_workers,
        )
        worker.finished.connect(self._on_workflow_finished)
        self._workflow_runner = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_handle,
        )

        self._output_panel.set_processing_active(True)
        self._output_panel.set_process_enabled(False)
        self._on_workflow_started()

    def _validate_parameters(self) -> bool:
        if not self._metadata:
            return True

        n_fovs = getattr(self._metadata, "n_fovs", 0)
        effective_fov_end = (
            n_fovs - 1 if self._output_panel.fov_end == -1 else self._output_panel.fov_end
        )

        if self._output_panel.fov_start < 0:
            return False
        if effective_fov_end < self._output_panel.fov_start:
            return False
        if effective_fov_end >= n_fovs:
            return False
        if self._output_panel.n_workers <= 0:
            return False
        return True

    @Slot(bool, str)
    def _on_workflow_finished(self, success: bool, message: str) -> None:
        logger.info(
            "Workflow finished (success=%s): %s",
            success,
            message or "No status message returned",
        )
        self._output_panel.set_processing_active(False)
        self._output_panel.set_process_enabled(True)
        self.processing_finished.emit()
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Processing failed: {message}")

    def _clear_workflow_handle(self) -> None:
        logger.info("Workflow thread finished")
        self._workflow_runner = None

    @Slot()
    def _on_workflow_started(self) -> None:
        logger.info("Workflow started from Processing tab")
        self.processing_started.emit()
        if self._status_manager:
            self._status_manager.show_message("Processing workflow started...")

    @Slot()
    def _on_merge_started(self) -> None:
        logger.info("Merge started from Processing tab")
        if self._status_manager:
            self._status_manager.show_message("Merging processing results...")

    @Slot(bool, str)
    def _on_merge_finished(self, success: bool, message: str) -> None:
        logger.info("Merge finished (success=%s): %s", success, message or "No message")
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Merge failed: {message}")

    @Slot()
    def _on_microscopy_loading_started(self) -> None:
        logger.info("Microscopy loading started from Processing tab")
        if self._status_manager:
            self._status_manager.show_message("Loading microscopy file...")

    @Slot(bool, str)
    def _on_microscopy_loading_finished(self, success: bool, message: str) -> None:
        logger.info(
            "Microscopy loading finished (success=%s): %s",
            success,
            message or "No message",
        )
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(
                    f"Failed to load microscopy file: {message}"
                )

    @Slot()
    def _on_samples_loading_started(self) -> None:
        logger.info("Samples loading started from Processing tab")
        if self._status_manager:
            self._status_manager.show_message("Loading samples...")

    @Slot(bool, str)
    def _on_samples_loading_finished(self, success: bool, message: str) -> None:
        logger.info(
            "Samples loading finished (success=%s): %s",
            success,
            message or "No message",
        )
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to load samples: {message}")

    @Slot()
    def _on_samples_saving_started(self) -> None:
        logger.info("Samples saving started from Processing tab")
        if self._status_manager:
            self._status_manager.show_message("Saving samples...")

    @Slot(bool, str)
    def _on_samples_saving_finished(self, success: bool, message: str) -> None:
        logger.info(
            "Samples saving finished (success=%s): %s",
            success,
            message or "No message",
        )
        if self._status_manager:
            if success:
                self._status_manager.show_message(message)
            else:
                self._status_manager.show_message(f"Failed to save samples: {message}")

    def is_processing(self) -> bool:
        return False

    def set_status_manager(self, status_manager) -> None:
        self._status_manager = status_manager
