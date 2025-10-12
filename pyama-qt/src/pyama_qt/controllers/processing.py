"""Controller coordinating processing UI actions and background work."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal

from pyama_core.io import MicroscopyMetadata, load_microscopy_file
from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    get_channels_from_yaml,
    get_time_units_from_yaml,
    load_processing_results_yaml,
)
from pyama_core.processing.workflow import ensure_context, run_complete_workflow
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext
from pyama_qt.models.processing import ProcessingModel
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.processing.page import ProcessingPage

from .processing_utils import parse_fov_range

logger = logging.getLogger(__name__)


# =============================================================================
# Merge Utility Functions
# =============================================================================


def get_available_features() -> list[str]:
    """Get list of available feature extractors."""
    try:
        from pyama_core.processing.extraction.feature import list_features

        return list_features()
    except ImportError:
        # Fallback for testing
        return ["intensity_total", "area"]


def read_yaml_config(path: Path) -> dict[str, Any]:
    """Read YAML config file with samples specification."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("YAML must contain a top-level 'samples' key")
        return data


def read_trace_csv(path: Path) -> list[dict[str, Any]]:
    """Read trace CSV file with dynamic feature columns."""
    df = get_dataframe(path)
    return df.to_dict("records")


def _format_timepoints(timepoints: Sequence[float]) -> str:
    values = list(timepoints)
    if not values:
        return "<none>"

    def _format_value(value: float) -> str:
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return f"{value:g}"

    if len(values) <= 4:
        return ", ".join(_format_value(v) for v in values)

    head = ", ".join(_format_value(v) for v in values[:3])
    tail = _format_value(values[-1])
    return f"{head}, ..., {tail}"


@dataclass(frozen=True)
class FeatureMaps:
    """Maps for feature data organized by (time, cell) tuples."""

    features: dict[
        str, dict[tuple[float, int], float]
    ]  # feature_name -> (time, cell) -> value
    times: list[float]
    cells: list[int]


def build_feature_maps(
    rows: list[dict[str, Any]], feature_names: list[str]
) -> FeatureMaps:
    """Build feature maps from trace CSV rows, filtering by 'good' column."""
    feature_maps: dict[str, dict[tuple[float, int], float]] = {}
    times_set = set()
    cells_set = set()

    # Initialize feature maps
    for feature_name in feature_names:
        feature_maps[feature_name] = {}

    # Process rows, filtering by 'good' column if it exists
    for r in rows:
        # Skip rows where 'good' column is False
        if "good" in r and not r["good"]:
            continue

        key = (r["time"], r["cell"])
        times_set.add(r["time"])
        cells_set.add(r["cell"])

        # Store feature values
        for feature_name in feature_names:
            if feature_name in r:
                feature_maps[feature_name][key] = r[feature_name]

    times = sorted(times_set)
    cells = sorted(cells_set)
    return FeatureMaps(feature_maps, times, cells)


def get_all_times(
    feature_maps_by_fov: dict[int, FeatureMaps], fovs: list[int]
) -> list[float]:
    """Get all unique time points across the specified FOVs."""
    all_times = set()
    for fov in fovs:
        if fov in feature_maps_by_fov:
            all_times.update(feature_maps_by_fov[fov].times)
    return sorted(all_times)


def parse_fovs_field(fovs_value) -> list[int]:
    """Parse FOV specification from various input types."""
    if isinstance(fovs_value, list):
        fovs = []
        for v in fovs_value:
            try:
                fov = int(v)
                if fov < 0:
                    raise ValueError(f"FOV value '{fov}' must be >= 0")
                fovs.append(fov)
            except (ValueError, TypeError) as e:
                raise ValueError(f"FOV value '{v}' is not a valid integer") from e
        return sorted(set(fovs))

    elif isinstance(fovs_value, str):
        if not fovs_value.strip():
            raise ValueError("FOV specification cannot be empty")
        return parse_fov_range(fovs_value)

    else:
        raise ValueError(
            "FOV spec must be a list of integers or a comma-separated string"
        )


def write_feature_csv(
    out_path: Path,
    times: list[float],
    fovs: list[int],
    feature_name: str,
    feature_maps_by_fov: dict[int, FeatureMaps],
    channel: int,
    time_units: str | None = None,
) -> None:
    """Write feature data to CSV file in wide format."""
    import pandas as pd

    # Create header: first column is time, then one column per cell across all FOVs
    all_cells = set()
    for fov in fovs:
        if fov in feature_maps_by_fov:
            all_cells.update(feature_maps_by_fov[fov].cells)

    all_cells_sorted = sorted(all_cells)

    # Create column names: cell IDs include FOV prefix
    columns = ["time"]
    for fov in fovs:
        for cell in all_cells_sorted:
            columns.append(f"fov_{fov:03d}_cell_{cell}")

    # Build rows
    rows = []
    for time in times:
        row = [time]
        for fov in fovs:
            feature_maps = feature_maps_by_fov.get(fov)
            for cell in all_cells_sorted:
                value = None
                if feature_maps and feature_name in feature_maps.features:
                    value = feature_maps.features[feature_name].get((time, cell))
                row.append(value)
        rows.append(row)

    # Create DataFrame and save
    df = pd.DataFrame(rows, columns=columns)

    # Add time units comment if provided
    if time_units:
        with out_path.open("w") as f:
            f.write(f"# Time units: {time_units}\n")
            df.to_csv(f, index=False, float_format="%.6f")
    else:
        df.to_csv(out_path, index=False, float_format="%.6f")


def _find_trace_csv_file(
    processing_results_data: dict[str, Any], input_dir: Path, fov: int, channel: int
) -> Path | None:
    """Find the trace CSV file for a specific FOV and channel."""
    # In the original YAML, FOV keys are simple strings like "0", "1", etc.
    fov_key = str(fov)
    # Use the original YAML structure under "results_paths"
    fov_data = processing_results_data.get("results_paths", {}).get(fov_key, {})

    traces_csv_list = fov_data.get("traces_csv", [])

    # Look for the specific channel in traces_csv list
    # traces_csv is a list of [channel, path] pairs
    for trace_item in traces_csv_list:
        if isinstance(trace_item, (list, tuple)) and len(trace_item) == 2:
            trace_channel, trace_path = trace_item
            if int(trace_channel) == channel:
                path = Path(trace_path)
                # If path is relative, resolve it relative to input_dir
                if not path.is_absolute():
                    path = input_dir / path

                # Check if an inspected version exists and prefer it
                inspected_path = path.with_name(path.stem + "_inspected" + path.suffix)
                if inspected_path.exists():
                    return inspected_path
                else:
                    return path

    return None


def _run_merge(
    sample_yaml: Path,
    processing_results: Path,
    output_dir: Path,
) -> str:
    """Internal merge logic - return success message or raise error.

    Args:
        sample_yaml: Path to sample YAML configuration
        processing_results: Path to processing_results.yaml
        output_dir: Directory for merged output files

    Returns:
        Success message with number of files created
    """
    # Input directory is always the parent of processing_results.yaml
    input_dir = processing_results.parent

    config = read_yaml_config(sample_yaml)
    samples = config["samples"]

    proc_results = load_processing_results_yaml(processing_results)
    channels = get_channels_from_yaml(proc_results)
    if not channels:
        raise ValueError("No fluorescence channels found in processing results")

    time_units = get_time_units_from_yaml(proc_results)

    # Load the original YAML data to access multi-channel traces_csv structure
    with processing_results.open("r", encoding="utf-8") as f:
        original_yaml_data = yaml.safe_load(f)

    available_features = get_available_features()

    all_fovs = set()
    for sample in samples:
        fovs = parse_fovs_field(sample.get("fovs", []))
        all_fovs.update(fovs)

    feature_maps_by_fov_channel = {}

    for fov in sorted(all_fovs):
        for channel in channels:
            csv_path = _find_trace_csv_file(original_yaml_data, input_dir, fov, channel)
            if csv_path is None or not csv_path.exists():
                logger.warning(f"No trace CSV for FOV {fov}, channel {channel}")
                continue

            rows = read_trace_csv(csv_path)
            feature_maps_by_fov_channel[(fov, channel)] = build_feature_maps(
                rows, available_features
            )

    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []
    total_samples = len(samples)
    total_channels = len(channels)
    total_features = len(available_features)

    logger.info(
        f"Starting merge for {total_samples} samples, {total_channels} channels, {total_features} features"
    )

    for sample in samples:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))
        logger.info(f"Processing sample '{sample_name}' with FOVs: {sample_fovs}")

        for channel in channels:
            channel_feature_maps = {}
            for fov in sample_fovs:
                key = (fov, channel)
                if key in feature_maps_by_fov_channel:
                    channel_feature_maps[fov] = feature_maps_by_fov_channel[key]

            if not channel_feature_maps:
                logger.warning(f"No data for sample {sample_name}, channel {channel}")
                continue

            times = get_all_times(channel_feature_maps, sample_fovs)
            logger.info(
                f"Sample '{sample_name}', channel {channel}: found {len(times)} time points across {len(channel_feature_maps)} FOVs"
            )

            for feature_name in available_features:
                output_filename = f"{sample_name}_{feature_name}_ch_{channel}.csv"
                output_path = output_dir / output_filename
                write_feature_csv(
                    output_path,
                    times,
                    sample_fovs,
                    feature_name,
                    channel_feature_maps,
                    channel,
                    time_units,
                )
                created_files.append(output_path)
                logger.info(f"Created: {output_filename}")

    logger.info("Merge completed successfully!")
    logger.info(f"Created {len(created_files)} files in {output_dir}:")
    for file_path in created_files:
        logger.info(f"  - {file_path.name}")

    return f"Merge completed. Created {len(created_files)} files in {output_dir}"


# =============================================================================
# Main Controller
# =============================================================================


class ProcessingController(QObject):
    """Controller coordinating processing workflow UI interactions."""

    def __init__(self, view: ProcessingPage, model: ProcessingModel) -> None:
        super().__init__()
        self._view = view
        self._model = model
        self._microscopy_loader: WorkerHandle | None = None
        self._workflow_runner: WorkerHandle | None = None
        self._merge_runner: WorkerHandle | None = None

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_view_state()

    # ------------------------------------------------------------------
    # Signal wiring helpers
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        config_panel = self._view.config_panel
        merge_panel = self._view.merge_panel

        config_panel.file_selected.connect(self._on_microscopy_selected)
        config_panel.output_dir_selected.connect(self._on_output_directory_selected)
        config_panel.channels_changed.connect(self._on_channels_changed)
        config_panel.parameters_changed.connect(self._on_parameters_changed)
        config_panel.process_requested.connect(self._on_process_requested)

        merge_panel.load_samples_requested.connect(self._on_samples_load_requested)
        merge_panel.save_samples_requested.connect(self._on_samples_save_requested)
        merge_panel.merge_requested.connect(self._on_merge_requested)

        # Connect path changes to merge model
        merge_panel.sample_yaml_path_changed.connect(self._on_sample_yaml_path_changed)
        merge_panel.processing_results_path_changed.connect(
            self._on_processing_results_path_changed
        )
        merge_panel.merge_output_dir_changed.connect(self._on_merge_output_dir_changed)

    def _on_sample_yaml_path_changed(self, path: Path | None) -> None:
        self._model.merge_model.sampleYamlPath = path

    def _on_processing_results_path_changed(self, path: Path | None) -> None:
        self._model.merge_model.processingResultsPath = path

    def _on_merge_output_dir_changed(self, path: Path | None) -> None:
        self._model.merge_model.mergeOutputDir = path

    def _connect_model_signals(self) -> None:
        config_panel = self._view.config_panel
        merge_panel = self._view.merge_panel

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

        # Connect merge model signals to view
        self._model.merge_model.sampleYamlPathChanged.connect(
            lambda path: merge_panel.set_sample_yaml_path(path) if path else None
        )
        self._model.merge_model.processingResultsPathChanged.connect(
            lambda path: merge_panel.set_processing_results_path(path) if path else None
        )
        self._model.merge_model.mergeOutputDirChanged.connect(
            lambda path: merge_panel.set_output_directory(path) if path else None
        )

    def _initialise_view_state(self) -> None:
        config_panel = self._view.config_panel
        merge_panel = self._view.merge_panel

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

        # Initialize merge panel
        if path := self._model.merge_model.sampleYamlPath:
            merge_panel.set_sample_yaml_path(path)
        if path := self._model.merge_model.processingResultsPath:
            merge_panel.set_processing_results_path(path)
        if path := self._model.merge_model.mergeOutputDir:
            merge_panel.set_output_directory(path)

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

    def _on_samples_load_requested(self, path: Path) -> None:
        self._load_samples(path)

    def _on_samples_save_requested(self, path: Path) -> None:
        try:
            samples = self._view.merge_panel.current_samples()
        except ValueError as exc:
            logger.error("Failed to save samples: %s", exc)
            self._model.workflow_model.errorMessage = str(exc)
            return
        self._save_samples(path, samples)

    def _on_merge_requested(self) -> None:
        """Handle merge request from view - reads paths from merge model."""
        # Read paths from merge model
        sample_yaml = self._model.merge_model.sampleYamlPath
        processing_results = self._model.merge_model.processingResultsPath
        output_dir = self._model.merge_model.mergeOutputDir

        # Validate all paths are present
        if not all([sample_yaml, processing_results, output_dir]):
            error_msg = "All paths must be specified for merge"
            logger.error(error_msg)
            self._model.workflow_model.errorMessage = error_msg
            return

        # Start merge with paths from merge model
        self._run_merge(sample_yaml, processing_results, output_dir)

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

    def _load_samples(self, path: Path) -> None:
        try:
            data = read_yaml_config(path)
            samples = data.get("samples", [])
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML: 'samples' must be list")
            self._view.merge_panel.load_samples(samples)
            # Update merge model with the loaded path
            self._model.merge_model.sampleYamlPath = path
        except Exception as exc:
            logger.error("Failed to load samples from %s: %s", path, exc)
            self._model.workflow_model.errorMessage = str(exc)

    def _save_samples(self, path: Path, samples: list[dict[str, Any]]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump({"samples": samples}, f, sort_keys=False)
            logger.info("Saved samples to %s", path)
            # Update merge model with the saved path
            self._model.merge_model.sampleYamlPath = path
        except Exception as exc:
            logger.error("Failed to save samples to %s: %s", path, exc)
            self._model.workflow_model.errorMessage = str(exc)

    def _run_merge(
        self, sample_yaml: Path, processing_results: Path, output_dir: Path
    ) -> None:
        if self._merge_runner:
            logger.warning("Merge already running")
            return

        worker = _MergeRunner(sample_yaml, processing_results, output_dir)
        worker.finished.connect(self._on_merge_finished)
        handle = start_worker(
            worker,
            start_method="run",
            finished_callback=self._clear_merge_handle,
        )
        self._merge_runner = handle
        self._model.workflow_model.statusMessage = "Running merge…"
        self._model.workflow_model.errorMessage = ""

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

    def _clear_merge_handle(self) -> None:
        logger.info("Merge thread finished")
        self._merge_runner = None

    def _on_merge_finished(self, success: bool, message: str) -> None:
        if success:
            logger.info("Merge completed: %s", message)
            self._model.workflow_model.set_status_message(message)
            self._model.workflow_model.set_error_message("")
        else:
            logger.error("Merge failed: %s", message)
            self._model.workflow_model.set_error_message(message)


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


class _MergeRunner(QObject):
    """Background worker for running merge operations."""

    finished = Signal(bool, str)

    def __init__(
        self, sample_yaml: Path, processing_results: Path, output_dir: Path
    ) -> None:
        super().__init__()
        self._sample_yaml = sample_yaml
        self._processing_results = processing_results
        self._output_dir = output_dir

    def run(self) -> None:
        try:
            message = _run_merge(
                self._sample_yaml,
                self._processing_results,
                self._output_dir,
            )
            self.finished.emit(True, message)
        except Exception as e:
            logger.exception("Merge failed")
            self.finished.emit(False, str(e))
