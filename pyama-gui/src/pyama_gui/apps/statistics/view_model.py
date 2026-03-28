"""View-model for the statistics tab."""

import logging
from pathlib import Path
from typing import TypedDict, cast

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama.apps.statistics.metrics import evaluate_onset_trace
from pyama.io.samples import discover_statistics_sample_pairs
from pyama.tasks import (
    StatisticsTaskRequest,
    TaskStatus,
    submit_statistics,
)
from pyama.types import SamplePair
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types.common import PageState, PlotSpec
from pyama_gui.types.statistics import StatisticsViewState

logger = logging.getLogger(__name__)

_METADATA_COLUMNS = {
    "sample",
    "position",
    "roi",
    "analysis_mode",
    "success",
    "success_auc",
    "success_onset",
    "n_points",
    "n_points_auc",
    "n_points_onset",
    "frame_interval_minutes",
    "fit_window_min",
    "normalization_mode",
    "source_intensity_file",
    "source_area_file",
    "time_start_min",
    "time_end_min",
}
_ONSET_METRICS = {"onset_time_min", "slope_min", "offset", "r_squared"}


class TracePlotData(TypedDict):
    lines_data: list[tuple[object, object]]
    styles_data: list[dict[str, object]]
    title: str
    y_label: str


class StatisticsWorker(TaskWorker):
    """Run folder statistics in the background."""

    def __init__(
        self,
        *,
        folder_path: Path,
        normalize_by_area: bool,
        frame_interval_minutes: float,
        fit_window_min: float,
        area_filter_size: int,
    ) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._normalize_by_area = normalize_by_area
        self._frame_interval_minutes = frame_interval_minutes
        self._fit_window_min = fit_window_min
        self._area_filter_size = area_filter_size

    def run(self) -> None:
        try:
            auc_results, traces_by_sample, auc_path = self._run_mode(
                mode="auc",
                progress_offset=0,
                progress_span=50,
            )
            onset_results, _, onset_path = self._run_mode(
                mode="onset_shifted_relu",
                progress_offset=50,
                progress_span=50,
            )
            merged_results = self._merge_results(auc_results, onset_results)
            self.emit_success(
                (merged_results, traces_by_sample, [auc_path, onset_path])
            )
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Statistics processing failed")
            self.emit_failure(str(exc))

    def _run_mode(
        self,
        *,
        mode: str,
        progress_offset: int,
        progress_span: int,
    ):
        record = submit_statistics(
            StatisticsTaskRequest(
                mode=mode,
                folder_path=self._folder_path,
                normalize_by_area=self._normalize_by_area,
                frame_interval_minutes=self._frame_interval_minutes,
                fit_window_min=self._fit_window_min,
                area_filter_size=self._area_filter_size,
            )
        )
        snapshot = self.wait_for_task(
            record,
            progress_handler=lambda progress: self.forward_progress(
                progress_offset + int((progress.percent or 0) * progress_span / 100),
                f"{mode}: {progress.message}",
            ),
        )
        if snapshot.status != TaskStatus.COMPLETED:
            raise RuntimeError(snapshot.error_message or f"{mode} statistics failed")
        return snapshot.result

    @staticmethod
    def _merge_results(
        auc_results: pd.DataFrame, onset_results: pd.DataFrame
    ) -> pd.DataFrame:
        merged = auc_results.merge(
            onset_results,
            on=["sample", "position", "roi"],
            how="outer",
            suffixes=("_auc", "_onset"),
        )
        for column in (
            "source_intensity_file",
            "source_area_file",
            "normalization_mode",
            "frame_interval_minutes",
            "fit_window_min",
            "time_start_min",
            "time_end_min",
        ):
            auc_column = f"{column}_auc"
            onset_column = f"{column}_onset"
            left = (
                merged[auc_column]
                if auc_column in merged.columns
                else pd.Series([pd.NA] * len(merged))
            )
            right = (
                merged[onset_column]
                if onset_column in merged.columns
                else pd.Series([pd.NA] * len(merged))
            )
            merged[column] = left.combine_first(right)
        if "success_auc" in merged.columns and "success_onset" in merged.columns:
            merged["success"] = merged["success_auc"].fillna(False).astype(
                bool
            ) & merged["success_onset"].fillna(False).astype(bool)
        return merged


class StatisticsViewModel(QObject):
    """Tab-level state and commands for statistics."""

    state_changed = Signal()
    results_changed = Signal()

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._workspace_dir = app_view_model.workspace_dir
        self._folder_path: Path | None = None
        self._sample_pairs: list[SamplePair] = []
        self._normalization_available = False
        self._normalize_by_area = False
        self._frame_interval_minutes = 10.0
        self._fit_window_min = 240.0
        self._area_filter_size = 10
        self._results_df: pd.DataFrame | None = None
        self._traces_by_sample: dict[str, pd.DataFrame] = {}
        self._saved_csv_paths: list[Path] = []
        self._selected_sample: str | None = None
        self._selected_cell: tuple[int, int] | None = None
        self._detail_page = 0
        self._selected_metric: str | None = None
        self._running = False
        self._worker_handle: WorkerHandle | None = None
        self.app_view_model.workspace_changed.connect(self._on_workspace_changed)
        self._sync_workspace_state()
        if self._workspace_dir is not None:
            self.load_workspace()

    @property
    def state(self) -> StatisticsViewState:
        comparison_plot = None
        grouped_values = self.grouped_metric_values
        if grouped_values:
            comparison_plot = PlotSpec(
                kind="boxplot",
                boxplot_groups=grouped_values,
                title=(
                    f"Comparison of {self._selected_metric}"
                    if self._selected_metric
                    else ""
                ),
                x_label="Sample",
                y_label=self._selected_metric or "",
            )
        return StatisticsViewState(
            sample_names=list(self.sample_names),
            normalization_available=self._normalization_available,
            normalize_by_area=self._normalize_by_area,
            frame_interval_minutes=self._frame_interval_minutes,
            fit_window_min=self._fit_window_min,
            area_filter_size=self._area_filter_size,
            running=self._running,
            selected_sample=self._selected_sample,
            selected_metric=self._selected_metric,
            metric_options=list(self.metric_options),
            detail_stats_text=self.detail_stats_text,
            detail_page=PageState(
                label=self.detail_page_label,
                can_previous=self.can_go_to_previous_detail_page,
                can_next=self.can_go_to_next_detail_page,
            ),
            visible_trace_ids=list(self.visible_trace_ids),
            trace_plot=self.selected_trace_plot,
            comparison_plot=comparison_plot,
            summary_rows=list(self.summary_rows),
        )

    @property
    def workspace_dir(self) -> Path | None:
        return self._workspace_dir

    @property
    def folder_path(self) -> Path | None:
        return self._folder_path

    @property
    def sample_pairs(self) -> list[SamplePair]:
        return list(self._sample_pairs)

    @property
    def sample_names(self) -> list[str]:
        return sorted(self._traces_by_sample)

    @property
    def normalization_available(self) -> bool:
        return self._normalization_available

    @property
    def mode(self) -> str:
        return "auc" if self._selected_metric == "auc" else "onset_shifted_relu"

    @property
    def normalize_by_area(self) -> bool:
        return self._normalize_by_area

    @property
    def frame_interval_minutes(self) -> float:
        return self._frame_interval_minutes

    @property
    def fit_window_min(self) -> float:
        return self._fit_window_min

    @property
    def area_filter_size(self) -> int:
        return self._area_filter_size

    @property
    def results_df(self) -> pd.DataFrame | None:
        return self._results_df

    @property
    def traces_by_sample(self) -> dict[str, pd.DataFrame]:
        return dict(self._traces_by_sample)

    @property
    def saved_csv_paths(self) -> list[Path]:
        return list(self._saved_csv_paths)

    @property
    def selected_sample(self) -> str | None:
        return self._selected_sample

    @property
    def selected_metric(self) -> str | None:
        return self._selected_metric

    @property
    def metric_options(self) -> list[tuple[str, str]]:
        if self._results_df is None:
            return [("AUC", "auc"), ("Onset", "onset_time_min")]
        options: list[tuple[str, str]] = []
        if "auc" in self._results_df.columns:
            options.append(("AUC", "auc"))
        if "onset_time_min" in self._results_df.columns:
            options.append(("Onset", "onset_time_min"))
        return options

    @property
    def grouped_metric_values(self) -> dict[str, list[float]]:
        if self._results_df is None or not self._selected_metric:
            return {}
        grouped_values: dict[str, list[float]] = {}
        for sample_name, sample_df in self._results_df.groupby("sample", sort=True):
            values = self._sample_metric_values(sample_df, self._selected_metric)
            grouped_values[str(sample_name)] = [
                float(value) for value in values.tolist()
            ]
        return grouped_values

    @property
    def summary_rows(self) -> list[tuple[str, int, float, float, float, float]]:
        if self._results_df is None or not self._selected_metric:
            return []
        rows: list[tuple[str, int, float, float, float, float]] = []
        for sample_name, sample_df in self._results_df.groupby("sample", sort=True):
            values = self._sample_metric_values(sample_df, self._selected_metric)
            if values.empty:
                continue
            q1 = float(values.quantile(0.25))
            q3 = float(values.quantile(0.75))
            rows.append(
                (
                    str(sample_name),
                    int(len(values)),
                    float(values.mean()),
                    float(values.std(ddof=0)),
                    float(values.median()),
                    q3 - q1,
                )
            )
        return rows

    @property
    def visible_trace_ids(self) -> list[tuple[int, int]]:
        groups = self._current_sample_position_groups()
        position_list = sorted(groups)
        if self._detail_page >= len(position_list):
            return []
        return groups.get(position_list[self._detail_page], [])

    @property
    def detail_page_label(self) -> str:
        groups = self._current_sample_position_groups()
        position_list = sorted(groups)
        total_pages = max(1, len(position_list))
        if self._detail_page < len(position_list):
            current_position = position_list[self._detail_page]
            roi_count = len(groups.get(current_position, []))
            return (
                f"Position {current_position} ({roi_count} ROIs) - "
                f"Page {self._detail_page + 1} of {total_pages}"
            )
        return f"Page {self._detail_page + 1} of {total_pages}"

    @property
    def can_go_to_previous_detail_page(self) -> bool:
        return self._detail_page > 0

    @property
    def can_go_to_next_detail_page(self) -> bool:
        return self._detail_page < max(
            0, len(self._current_sample_position_groups()) - 1
        )

    @property
    def detail_stats_text(self) -> str:
        sample_results = self._sample_results()
        if (
            sample_results is None
            or sample_results.empty
            or self._selected_sample is None
        ):
            return ""
        auc_values = pd.to_numeric(sample_results["auc"], errors="coerce").dropna()
        if "onset_time_min" in sample_results.columns:
            onset_values = pd.to_numeric(
                sample_results["onset_time_min"], errors="coerce"
            ).dropna()
        else:
            onset_values = pd.Series(dtype=float)
        auc_text = (
            f"AUC median={auc_values.median():.3f}"
            if not auc_values.empty
            else "AUC median=n/a"
        )
        onset_text = (
            f"Onset median={onset_values.median():.3f} min"
            if not onset_values.empty
            else "Onset median=n/a"
        )
        return f"Sample {self._selected_sample}: {auc_text}, {onset_text}"

    @property
    def selected_trace_plot_data(self) -> TracePlotData | None:
        if self._selected_sample is None or self._selected_cell is None:
            return None
        trace_df = self._traces_by_sample.get(self._selected_sample)
        sample_results = self._sample_results()
        if trace_df is None or sample_results is None:
            return None
        position, roi = self._selected_cell
        try:
            cell_df = trace_df.loc[(position, roi)].sort_values("frame")
        except KeyError:
            return None

        time_values = cell_df["time_min"].to_numpy()
        trace_values = cell_df["value"].to_numpy()
        lines_data: list[tuple[object, object]] = [(time_values, trace_values)]
        styles_data: list[dict[str, object]] = [
            {
                "color": "blue",
                "alpha": 0.8,
                "label": f"Position {position}, ROI {roi}",
                "linewidth": 1.5,
            }
        ]

        row = self.result_row_for_cell(position, roi)
        title = f"{self._selected_sample}: Position {position}, ROI {roi}"
        if row is not None:
            title_parts = []
            if row.get("auc") is not None:
                title_parts.append(f"AUC={row['auc']:.3f}")
            if row.get("onset_time_min") is not None:
                title_parts.append(f"Onset={row['onset_time_min']:.3f}")
            if title_parts:
                title = f"{title} ({', '.join(title_parts)})"
            if (
                bool(row.get("success_onset", False))
                and row.get("onset_time_min") is not None
                and row.get("slope_min") is not None
                and row.get("offset") is not None
            ):
                fit_window_min = float(
                    pd.to_numeric(
                        pd.Series([row.get("fit_window_min", time_values.max())]),
                        errors="coerce",
                    ).iloc[0]
                )
                fit_mask = pd.notna(time_values) & (time_values <= fit_window_min)
                fit_time_values = time_values[fit_mask]
                fitted_trace = evaluate_onset_trace(
                    fit_time_values,
                    float(row["onset_time_min"]),
                    float(row["slope_min"]),
                    float(row["offset"]),
                )
                label = "Shifted ReLU"
                if row.get("r_squared") is not None:
                    label = f"{label} (R²={row['r_squared']:.3f})"
                lines_data.append((fit_time_values, fitted_trace))
                styles_data.append(
                    {
                        "color": "red",
                        "alpha": 0.8,
                        "label": label,
                        "linewidth": 2.0,
                    }
                )
        return {
            "lines_data": lines_data,
            "styles_data": styles_data,
            "title": title,
            "y_label": (
                "Normalized intensity / area"
                if self._normalize_by_area
                else "Intensity total"
            ),
        }

    @property
    def selected_trace_plot(self) -> PlotSpec | None:
        plot_data = self.selected_trace_plot_data
        if plot_data is None:
            return None
        return PlotSpec(
            kind="lines",
            lines_data=plot_data["lines_data"],
            styles_data=plot_data["styles_data"],
            title=plot_data["title"],
            x_label="Time (min)",
            y_label=plot_data["y_label"],
        )

    @property
    def running(self) -> bool:
        return self._running

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self._sync_workspace_state()
        if path is not None:
            self.load_workspace()

    def _sync_workspace_state(self) -> None:
        if self._workspace_dir is None:
            self._folder_path = None
        else:
            self._folder_path = self._workspace_dir / "traces_merged"
        self._sample_pairs = []
        self._normalization_available = False
        self._normalize_by_area = False
        self.clear_results()
        self.state_changed.emit()

    def set_normalize_by_area(self, normalize_by_area: bool) -> None:
        self._normalize_by_area = normalize_by_area and self._normalization_available
        self.clear_results()
        self.state_changed.emit()

    def set_frame_interval_minutes(self, value: float) -> None:
        self._frame_interval_minutes = value
        self.clear_results()
        self.state_changed.emit()

    def set_fit_window_min(self, value: float) -> None:
        self._fit_window_min = value
        self.clear_results()
        self.state_changed.emit()

    def set_area_filter_size(self, value: int) -> None:
        self._area_filter_size = value
        self.clear_results()
        self.state_changed.emit()

    def set_selected_sample(self, sample_name: str) -> None:
        if not sample_name or sample_name == self._selected_sample:
            return
        self._selected_sample = sample_name
        self._selected_cell = None
        self._detail_page = 0
        visible_ids = self.visible_trace_ids
        if visible_ids:
            self._selected_cell = visible_ids[0]
        self.results_changed.emit()
        self.state_changed.emit()

    def set_selected_cell(self, cell_id: tuple[int, int]) -> None:
        if self._selected_cell == cell_id:
            return
        self._selected_cell = cell_id
        self.results_changed.emit()

    def set_selected_metric(self, metric_name: str) -> None:
        if not metric_name or metric_name == self._selected_metric:
            return
        self._selected_metric = metric_name
        self.results_changed.emit()

    def previous_detail_page(self) -> None:
        if self._detail_page <= 0:
            return
        self._detail_page -= 1
        self._selected_cell = (
            self.visible_trace_ids[0] if self.visible_trace_ids else None
        )
        self.results_changed.emit()
        self.state_changed.emit()

    def next_detail_page(self) -> None:
        if not self.can_go_to_next_detail_page:
            return
        self._detail_page += 1
        self._selected_cell = (
            self.visible_trace_ids[0] if self.visible_trace_ids else None
        )
        self.results_changed.emit()
        self.state_changed.emit()

    def clear_results(self) -> None:
        self._results_df = None
        self._traces_by_sample = {}
        self._saved_csv_paths = []
        self._selected_sample = None
        self._selected_cell = None
        self._detail_page = 0
        self._selected_metric = "auc"
        self.results_changed.emit()

    def load_workspace(self) -> None:
        if self._running:
            return
        if self._folder_path is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return
        try:
            sample_pairs = discover_statistics_sample_pairs(self._folder_path)
        except Exception as exc:
            logger.warning(
                "Failed to load statistics folder %s: %s", self._folder_path, exc
            )
            self._sample_pairs = []
            self._normalization_available = False
            self.clear_results()
            self.state_changed.emit()
            self.app_view_model.set_status_message(
                f"Failed to load statistics folder: {exc}"
            )
            return

        self._sample_pairs = sample_pairs
        self._normalization_available = bool(sample_pairs) and all(
            pair.area_csv is not None for pair in sample_pairs
        )
        if not self._normalization_available:
            self._normalize_by_area = False
        self.clear_results()
        self.state_changed.emit()
        if self._normalization_available:
            self.app_view_model.set_status_message(
                f"Loaded statistics folder {self._folder_path.name} with {len(sample_pairs)} samples"
            )
        else:
            self.app_view_model.set_status_message(
                f"Loaded statistics folder {self._folder_path.name} with "
                f"{len(sample_pairs)} samples; area normalization disabled because at least one sample has no area CSV"
            )

    def run_statistics(self) -> None:
        if self._running:
            return
        if self._folder_path is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return
        if not self._sample_pairs:
            self.app_view_model.set_status_message(
                "No valid sample pairs were found in this folder."
            )
            return

        worker = StatisticsWorker(
            folder_path=self._folder_path,
            normalize_by_area=self._normalize_by_area,
            frame_interval_minutes=self._frame_interval_minutes,
            fit_window_min=self._fit_window_min,
            area_filter_size=self._area_filter_size,
        )
        worker.progress_value.connect(self._on_statistics_progress)
        worker.finished.connect(self._on_statistics_finished)
        self._worker_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_worker_handle,
        )
        self._running = True
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Running statistics...")

    def _on_statistics_finished(
        self, success: bool, result: object, message: str
    ) -> None:
        self._running = False
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if not success:
            logger.error("Statistics processing failed: %s", message)
            self.app_view_model.set_status_message(message)
            return

        if not (
            isinstance(result, tuple)
            and len(result) == 3
            and isinstance(result[0], pd.DataFrame)
            and isinstance(result[1], dict)
            and isinstance(result[2], list)
        ):
            self.app_view_model.set_status_message(
                "Statistics returned an invalid result."
            )
            return
        self._results_df, self._traces_by_sample, self._saved_csv_paths = cast(
            tuple[pd.DataFrame, dict[str, pd.DataFrame], list[Path]],
            result,
        )
        sample_names = self.sample_names
        self._selected_sample = sample_names[0] if sample_names else None
        self._selected_metric = self._preferred_metric()
        self._detail_page = 0
        visible_ids = self.visible_trace_ids
        self._selected_cell = visible_ids[0] if visible_ids else None
        self.results_changed.emit()

        normalization_label = (
            "area-normalized" if self._normalize_by_area else "raw intensity"
        )
        save_names = ", ".join(path.name for path in self._saved_csv_paths) or "results"
        self.app_view_model.set_status_message(
            f"Statistics ({normalization_label}) saved to {save_names}"
        )

    def _on_statistics_progress(self, percent: int, message: str) -> None:
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def result_row_for_cell(
        self, position: int, roi: int
    ) -> dict[str, float | bool | str] | None:
        sample_results = self._sample_results()
        if sample_results is None:
            return None
        row_df = sample_results[
            (sample_results["position"] == position) & (sample_results["roi"] == roi)
        ]
        if row_df.empty:
            return None
        row = row_df.iloc[0]
        result: dict[str, float | bool | str] = {}
        for key, value in row.items():
            if pd.isna(value):
                continue
            result[str(key)] = value
        return result

    def _clear_worker_handle(self) -> None:
        self._worker_handle = None

    def _sample_results(self) -> pd.DataFrame | None:
        if self._results_df is None or self._selected_sample is None:
            return None
        return self._results_df[self._results_df["sample"] == self._selected_sample]

    def _current_sample_position_groups(self) -> dict[int, list[tuple[int, int]]]:
        sample_results = self._sample_results()
        groups: dict[int, list[tuple[int, int]]] = {}
        if sample_results is None or sample_results.empty:
            return groups
        for _, row in sample_results.iterrows():
            position = int(row["position"])
            roi = int(row["roi"])
            groups.setdefault(position, []).append((position, roi))
        for position in groups:
            groups[position].sort(key=lambda value: value[1])
        return groups

    def _preferred_metric(self) -> str | None:
        metrics = [value for _label, value in self.metric_options]
        if "auc" in metrics:
            return "auc"
        if "onset_time_min" in metrics:
            return "onset_time_min"
        return metrics[0] if metrics else None

    @staticmethod
    def _sample_metric_values(sample_df: pd.DataFrame, metric_name: str) -> pd.Series:
        values = pd.to_numeric(sample_df[metric_name], errors="coerce").dropna()
        success_column = "success_auc" if metric_name == "auc" else "success_onset"
        if success_column in sample_df.columns:
            success_mask = sample_df[success_column].fillna(False).astype(bool)
            values = pd.to_numeric(
                sample_df.loc[success_mask, metric_name], errors="coerce"
            ).dropna()
        return values
