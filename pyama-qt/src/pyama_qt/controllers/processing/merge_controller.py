"""Controller for merge UI actions and background work."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtCore import QObject, Signal

from pyama_core.io.processing_csv import get_dataframe
from pyama_core.io.results_yaml import (
    get_channels_from_yaml,
    get_time_units_from_yaml,
    load_processing_results_yaml,
)
from pyama_qt.models.processing import ProcessingModel
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.processing.page import ProcessingPage

logger = logging.getLogger(__name__)


def parse_fov_range(text: str) -> list[int]:
    """Parse FOV specification like '0-5, 7, 9-11' into list of integers."""
    if not text.strip():
        return []

    normalized = text.replace(" ", "")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs (semicolons not allowed)")

    fovs = []
    parts = [p for p in normalized.split(",") if p]

    for part in parts:
        if "-" in part:
            try:
                start_str, end_str = part.split("-", 1)
                if not start_str or not end_str:
                    raise ValueError(f"Invalid range '{part}': missing start or end")

                start, end = int(start_str), int(end_str)
                if start < 0 or end < 0:
                    raise ValueError(
                        f"Invalid range '{part}': negative values not allowed"
                    )
                if start > end:
                    raise ValueError(f"Invalid range '{part}': start must be <= end")

                fovs.extend(range(start, end + 1))
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid range '{part}': must be integers") from e
                raise
        else:
            try:
                fov = int(part)
                if fov < 0:
                    raise ValueError(f"FOV '{part}' must be >= 0")
                fovs.append(fov)
            except ValueError:
                raise ValueError(f"FOV '{part}' must be a non-negative integer")

    return sorted(set(fovs))


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


class MergeController(QObject):
    """Controller coordinating merge UI actions and background work."""

    def __init__(self, view: ProcessingPage, model: ProcessingModel) -> None:
        super().__init__()
        self._view = view
        self._model = model
        self._merge_runner: WorkerHandle | None = None

        self._connect_view_signals()
        self._connect_model_signals()

    def _connect_view_signals(self) -> None:
        merge_panel = self._view.merge_panel

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
        merge_panel = self._view.merge_panel

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
        self._model.workflow_model.statusMessage = "Running merge2026..."
        self._model.workflow_model.errorMessage = ""

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
