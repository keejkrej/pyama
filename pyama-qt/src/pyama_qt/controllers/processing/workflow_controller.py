"""Controller for workflow processing UI actions and background work."""

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from pyama_core.io import MicroscopyMetadata, load_microscopy_file
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext
from pyama_qt.models.processing import ProcessingModel
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.processing.page import ProcessingPage

logger = logging.getLogger(__name__)


class WorkflowController(QObject):
    """Controller coordinating workflow processing UI interactions."""

    def __init__(self, view: ProcessingPage, model: ProcessingModel) -> None:
        super().__init__()
        self._view = view
        self._model = model
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_view_state()

    # ------------------------------------------------------------------
    # Signal wiring helpers
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        config_panel = self._view.config_panel

        config_panel.file_selected.connect(self._on_microscopy_selected)
        config_panel.output_dir_selected.connect(self._on_output_directory_selected)
        config_panel.channels_changed.connect(self._on_channels_changed)
        config_panel.parameters_changed.connect(self._on_parameters_changed)
        config_panel.process_requested.connect(self._on_process_requested)

    def _connect_model_signals(self) -> None:
        config_panel = self._view.config_panel

        self._model.workflow_model.microscopyPathChanged.connect(
            config_panel.display_microscopy_path
        )
        self._model.workflow_model.outputDirChanged.connect(
            config_panel.display_output_directory
        )
        self._model.workflow_model.metadataChanged.connect(self._on_metadata_changed)
        self._model.workflow_model.phaseChanged.connect(self._sync_channel_selection)
        self._model.workflow_model.fluorescenceChanged.connect(
            self._sync_channel_selection
        )
        self._model.workflow_model.fovStartChanged.connect(
            lambda value: config_panel.set_parameter_value("fov_start", value)
        )
        self._model.workflow_model.fovEndChanged.connect(
            lambda value: config_panel.set_parameter_value("fov_end", value)
        )
        self._model.workflow_model.batchSizeChanged.connect(
            lambda value: config_panel.set_parameter_value("batch_size", value)
        )
        self._model.workflow_model.nWorkersChanged.connect(
            lambda value: config_panel.set_parameter_value("n_workers", value)
        )

        self._model.workflow_model.isProcessingChanged.connect(
            config_panel.set_processing_active
        )
        self._model.workflow_model.isProcessingChanged.connect(
            lambda active: config_panel.set_process_enabled(not active)
        )

    def _initialise_view_state(self) -> None:
        config_panel = self._view.config_panel

        # Initialize config panel
        config_panel.display_microscopy_path(self._model.workflow_model.microscopyPath)
        config_panel.display_output_directory(self._model.workflow_model.outputDir)
        self._on_metadata_changed(self._model.workflow_model.metadata)
        self._sync_channel_selection()
        config_panel.set_parameter_value(
            "fov_start", self._model.workflow_model.fovStart
        )
        config_panel.set_parameter_value("fov_end", self._model.workflow_model.fovEnd)
        config_panel.set_parameter_value(
            "batch_size", self._model.workflow_model.batchSize
        )
        config_panel.set_parameter_value(
            "n_workers", self._model.workflow_model.nWorkers
        )
        active = self._model.workflow_model.isProcessing
        config_panel.set_processing_active(active)
        config_panel.set_process_enabled(not active)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_microscopy_selected(self, path: Path) -> None:
        self._load_microscopy(path)

    def _on_output_directory_selected(self, directory: Path) -> None:
        logger.info("Selected output directory: %s", directory)
        self._model.workflow_model.outputDir = directory
        self._model.workflow_model.errorMessage = ""

    def _on_channels_changed(self, payload: Any) -> None:
        phase = getattr(payload, "phase", None)
        fluorescence = list(getattr(payload, "fluorescence", [])) if payload else []
        self._model.workflow_model.update_channels(phase, fluorescence)

    def _on_parameters_changed(self, param_dict: dict[str, Any]) -> None:
        fov_start = param_dict.get("fov_start", -1)
        fov_end = param_dict.get("fov_end", -1)
        batch_size = param_dict.get("batch_size", 2)
        n_workers = param_dict.get("n_workers", 2)
        self._model.workflow_model.update_parameters(
            fov_start=fov_start,
            fov_end=fov_end,
            batch_size=batch_size,
            n_workers=n_workers,
        )

    def _on_process_requested(self) -> None:
        if self._model.workflow_model.isProcessing:
            logger.warning("Workflow already running; ignoring start request")
            return

        try:
            self._validate_ready()
        except ValueError as exc:
            logger.error("Cannot start workflow: %s", exc)
            self._model.workflow_model.errorMessage = str(exc)
            return

        metadata = self._model.workflow_model.metadata()
        assert metadata is not None

        context = ProcessingContext(
            output_dir=self._model.workflow_model.outputDir,
            channels=Channels(
                pc=(
                    self._model.workflow_model.phase
                    if self._model.workflow_model.phase is not None
                    else 0
                ),
                fl=list(self._model.workflow_model.fluorescence or []),
            ),
            params={},
            time_units="",
        )

        worker = _WorkflowRunner(
            metadata=metadata,
            context=context,
            fov_start=self._model.workflow_model.fovStart,
            fov_end=self._model.workflow_model.fovEnd,
            batch_size=self._model.workflow_model.batchSize,
            n_workers=self._model.workflow_model.nWorkers,
        )
        worker.finished.connect(self._on_workflow_finished)

        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_workflow_handle,
        )
        self._workflow_runner = handle
        self._model.workflow_model.isProcessing = True
        self._model.workflow_model.statusMessage = "Running workflow…"
        self._model.workflow_model.errorMessage = ""

    # ------------------------------------------------------------------
    # Model → Controller helpers
    # ------------------------------------------------------------------
    def _sync_channel_selection(self, *_args) -> None:
        selection = self._model.workflow_model.channels()
        self._view.config_panel.apply_selected_channels(
            phase=selection.phase,
            fluorescence=selection.fluorescence,
        )

    def _on_metadata_changed(self, metadata) -> None:
        channel_names = getattr(metadata, "channel_names", None) if metadata else None
        phase_options: list[tuple[str, int | None]] = [("None", None)]
        fluorescence_options: list[tuple[str, int]] = []
        if channel_names:
            for idx, name in enumerate(channel_names):
                label = f"Channel {idx}: {name}"
                phase_options.append((label, idx))
                fluorescence_options.append((label, idx))
        self._view.config_panel.set_channel_options(
            phase_channels=phase_options,
            fluorescence_channels=fluorescence_options,
        )
        self._sync_channel_selection()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_microscopy(self, path: Path) -> None:
        logger.info("Loading microscopy metadata from %s", path)
        self._model.workflow_model.load_microscopy(path)
        self._model.workflow_model.statusMessage = "Loading microscopy metadata…"
        self._model.workflow_model.errorMessage = ""

        worker = _MicroscopyLoaderWorker(path)
        worker.loaded.connect(self._on_microscopy_loaded)
        worker.failed.connect(self._on_microscopy_failed)
        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._on_loader_finished,
        )
        self._microscopy_loader = handle

    def _validate_ready(self) -> None:
        metadata = self._model.workflow_model.metadata
        if metadata is None:
            raise ValueError("Load an ND2 file before starting the workflow")
        if self._model.workflow_model.outputDir is None:
            raise ValueError("Select an output directory before starting the workflow")
        channels = self._model.workflow_model.channels()
        if channels.phase is None and not channels.fluorescence:
            raise ValueError("Select at least one channel to process")

        params = self._model.workflow_model.parameters()
        n_fovs = getattr(metadata, "n_fovs", 0)

        if params.fov_start != -1 or params.fov_end != -1:
            if params.fov_start < 0:
                raise ValueError("FOV start must be >= 0 or -1 for all")
            if params.fov_end < params.fov_start:
                raise ValueError("FOV end must be >= start")
            if params.fov_end >= n_fovs:
                raise ValueError(
                    f"FOV end ({params.fov_end}) must be less than total FOVs ({n_fovs})"
                )

        if params.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if params.n_workers <= 0:
            raise ValueError("Number of workers must be positive")

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_microscopy_loaded(self, metadata: MicroscopyMetadata) -> None:
        logger.info("Microscopy metadata loaded")
        self._model.workflow_model.metadata = metadata
        self._model.workflow_model.statusMessage = "ND2 ready"
        self._model.workflow_model.errorMessage = ""

    def _on_microscopy_failed(self, message: str) -> None:
        logger.error("Failed to load ND2: %s", message)
        self._model.workflow_model.set_status_message("")
        self._model.workflow_model.set_error_message(message)

    def _on_loader_finished(self) -> None:
        logger.info("ND2 loader thread finished")
        self._microscopy_loader = None

    def _on_workflow_finished(self, success: bool, message: str) -> None:
        logger.info("Workflow finished (success=%s): %s", success, message)
        self._model.workflow_model.set_is_processing(False)
        self._model.workflow_model.set_status_message(message)
        if not success:
            self._model.workflow_model.set_error_message(message)

    def _clear_workflow_handle(self) -> None:
        logger.info("Workflow thread finished")
        self._workflow_runner = None


# =============================================================================
# Background Worker Classes
# =============================================================================


class _MicroscopyLoaderWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()  # Signal to indicate work is complete

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._cancelled = False

    def cancel(self) -> None:
        """Mark this worker as cancelled."""
        self._cancelled = True

    def run(self) -> None:
        try:
            if self._cancelled:
                self.finished.emit()
                return
            _img, metadata = load_microscopy_file(self._path)
            if not self._cancelled:
                self.loaded.emit(metadata)
        except Exception as exc:  # pragma: no cover - propagate to UI
            if not self._cancelled:
                self.failed.emit(str(exc))
        finally:
            # Always emit finished to quit the thread
            self.finished.emit()


class _WorkflowRunner(QObject):
    finished = Signal(bool, str)

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        fov_start: int,
        fov_end: int,
        batch_size: int,
        n_workers: int,
    ) -> None:
        super().__init__()
        self._metadata = metadata
        self._context = ensure_context(context)
        self._fov_start = fov_start
        self._fov_end = fov_end
        self._batch_size = batch_size
        self._n_workers = n_workers

    def run(self) -> None:
        try:
            success = run_complete_workflow(
                self._metadata,
                self._context,
                fov_start=self._fov_start,
                fov_end=self._fov_end,
                batch_size=self._batch_size,
                n_workers=self._n_workers,
            )
            if success:
                output_dir = self._context.output_dir or "output directory"
                message = f"Results saved to {output_dir}"
                self.finished.emit(True, message)
            else:  # pragma: no cover - defensive branch
                self.finished.emit(False, "Workflow reported failure")
        except Exception as exc:  # pragma: no cover - propagate to UI
            logger.exception("Workflow execution failed")
            self.finished.emit(False, f"Workflow error: {exc}")
