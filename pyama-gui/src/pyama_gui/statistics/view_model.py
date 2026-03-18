"""View-model for the statistics tab."""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama.tasks import discover_sample_pairs, evaluate_onset_trace, run_folder_statistics
from pyama.types import SamplePair
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task

logger = logging.getLogger(__name__)

_METADATA_COLUMNS = {
    "sample",
    "fov",
    "cell",
    "analysis_mode",
    "success",
    "success_auc",
    "success_onset",
    "n_points",
    "n_points_auc",
    "n_points_onset",
    "fit_window_hours",
    "normalization_mode",
    "source_intensity_file",
    "source_area_file",
    "time_start",
    "time_end",
}
_ONSET_METRICS = {"onset_time", "slope", "offset", "r_squared"}


class StatisticsWorker(TaskWorker):
    """Run folder statistics in the background."""

    def __init__(
        self,
        *,
        folder_path: Path,
        normalize_by_area: bool,
        fit_window_hours: float,
        area_filter_size: int,
    ) -> None:
        super().__init__()
        self._folder_path = folder_path
        self._normalize_by_area = normalize_by_area
        self._fit_window_hours = fit_window_hours
        self._area_filter_size = area_filter_size

    def run(self) -> None:
        try:
            auc_results, traces_by_sample, auc_path = run_folder_statistics(
                self._folder_path,
                "auc",
                normalize_by_area=self._normalize_by_area,
                fit_window_hours=self._fit_window_hours,
                area_filter_size=self._area_filter_size,
            )
            onset_results, _, onset_path = run_folder_statistics(
                self._folder_path,
                "onset_shifted_relu",
                normalize_by_area=self._normalize_by_area,
                fit_window_hours=self._fit_window_hours,
                area_filter_size=self._area_filter_size,
            )
            merged_results = self._merge_results(auc_results, onset_results)
            self.emit_success((merged_results, traces_by_sample, [auc_path, onset_path]))
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Statistics processing failed")
            self.emit_failure(str(exc))

    @staticmethod
    def _merge_results(auc_results: pd.DataFrame, onset_results: pd.DataFrame) -> pd.DataFrame:
        merged = auc_results.merge(
            onset_results,
            on=["sample", "fov", "cell"],
            how="outer",
            suffixes=("_auc", "_onset"),
        )
        for column in (
            "source_intensity_file",
            "source_area_file",
            "normalization_mode",
            "fit_window_hours",
            "time_start",
            "time_end",
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
            merged["success"] = (
                merged["success_auc"].fillna(False).astype(bool)
                & merged["success_onset"].fillna(False).astype(bool)
            )
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
        self._fit_window_hours = 4.0
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
    def fit_window_hours(self) -> float:
        return self._fit_window_hours

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
            return [("AUC", "auc"), ("Onset", "onset_time")]
        options: list[tuple[str, str]] = []
        if "auc" in self._results_df.columns:
            options.append(("AUC", "auc"))
        if "onset_time" in self._results_df.columns:
            options.append(("Onset", "onset_time"))
        return options

    @property
    def grouped_metric_values(self) -> dict[str, list[float]]:
        if self._results_df is None or not self._selected_metric:
            return {}
        grouped_values: dict[str, list[float]] = {}
        for sample_name, sample_df in self._results_df.groupby("sample", sort=True):
            values = self._sample_metric_values(sample_df, self._selected_metric)
            grouped_values[sample_name] = values.tolist()
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
                    sample_name,
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
        groups = self._current_sample_fov_groups()
        fov_list = sorted(groups)
        if self._detail_page >= len(fov_list):
            return []
        return groups.get(fov_list[self._detail_page], [])

    @property
    def detail_page_label(self) -> str:
        groups = self._current_sample_fov_groups()
        fov_list = sorted(groups)
        total_pages = max(1, len(fov_list))
        if self._detail_page < len(fov_list):
            current_fov = fov_list[self._detail_page]
            cell_count = len(groups.get(current_fov, []))
            return (
                f"FOV {current_fov} ({cell_count} cells) - "
                f"Page {self._detail_page + 1} of {total_pages}"
            )
        return f"Page {self._detail_page + 1} of {total_pages}"

    @property
    def can_go_to_previous_detail_page(self) -> bool:
        return self._detail_page > 0

    @property
    def can_go_to_next_detail_page(self) -> bool:
        return self._detail_page < max(0, len(self._current_sample_fov_groups()) - 1)

    @property
    def detail_stats_text(self) -> str:
        sample_results = self._sample_results()
        if sample_results is None or sample_results.empty or self._selected_sample is None:
            return ""
        auc_values = pd.to_numeric(sample_results["auc"], errors="coerce").dropna()
        if "onset_time" in sample_results.columns:
            onset_values = pd.to_numeric(
                sample_results["onset_time"], errors="coerce"
            ).dropna()
        else:
            onset_values = pd.Series(dtype=float)
        auc_text = f"AUC median={auc_values.median():.3f}" if not auc_values.empty else "AUC median=n/a"
        onset_text = (
            f"Onset median={onset_values.median():.3f}"
            if not onset_values.empty
            else "Onset median=n/a"
        )
        return f"Sample {self._selected_sample}: {auc_text}, {onset_text}"

    @property
    def selected_trace_plot_data(self) -> dict[str, object] | None:
        if self._selected_sample is None or self._selected_cell is None:
            return None
        trace_df = self._traces_by_sample.get(self._selected_sample)
        sample_results = self._sample_results()
        if trace_df is None or sample_results is None:
            return None
        fov, cell = self._selected_cell
        try:
            cell_df = trace_df.loc[(fov, cell)].sort_values("time")
        except KeyError:
            return None

        time_values = cell_df["time"].to_numpy()
        trace_values = cell_df["value"].to_numpy()
        lines_data = [(time_values, trace_values)]
        styles_data = [
            {
                "color": "blue",
                "alpha": 0.8,
                "label": f"FOV {fov}, Cell {cell}",
                "linewidth": 1.5,
            }
        ]

        row = self.result_row_for_cell(fov, cell)
        title = f"{self._selected_sample}: FOV {fov}, Cell {cell}"
        if row is not None:
            title_parts = []
            if row.get("auc") is not None:
                title_parts.append(f"AUC={row['auc']:.3f}")
            if row.get("onset_time") is not None:
                title_parts.append(f"Onset={row['onset_time']:.3f}")
            if title_parts:
                title = f"{title} ({', '.join(title_parts)})"
            if (
                bool(row.get("success_onset", False))
                and row.get("onset_time") is not None
                and row.get("slope") is not None
                and row.get("offset") is not None
            ):
                fit_window_hours = float(
                    pd.to_numeric(
                        pd.Series([row.get("fit_window_hours", time_values.max())]),
                        errors="coerce",
                    ).iloc[0]
                )
                fit_mask = pd.notna(time_values) & (time_values <= fit_window_hours)
                fit_time_values = time_values[fit_mask]
                fitted_trace = evaluate_onset_trace(
                    fit_time_values,
                    float(row["onset_time"]),
                    float(row["slope"]),
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
    def running(self) -> bool:
        return self._running

    def _on_workspace_changed(self, path: Path | None) -> None:
        self._workspace_dir = path
        self._sync_workspace_state()
        if path is not None:
            self.load_workspace()

    def _sync_workspace_state(self) -> None:
        self._folder_path = None if self._workspace_dir is None else self._workspace_dir / "merge_output"
        self._sample_pairs = []
        self._normalization_available = False
        self._normalize_by_area = False
        self.clear_results()
        self.state_changed.emit()

    def set_normalize_by_area(self, normalize_by_area: bool) -> None:
        self._normalize_by_area = normalize_by_area and self._normalization_available
        self.clear_results()
        self.state_changed.emit()

    def set_fit_window_hours(self, value: float) -> None:
        self._fit_window_hours = value
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
        self._selected_cell = self.visible_trace_ids[0] if self.visible_trace_ids else None
        self.results_changed.emit()
        self.state_changed.emit()

    def next_detail_page(self) -> None:
        if not self.can_go_to_next_detail_page:
            return
        self._detail_page += 1
        self._selected_cell = self.visible_trace_ids[0] if self.visible_trace_ids else None
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
            sample_pairs = discover_sample_pairs(self._folder_path)
        except Exception as exc:
            logger.warning("Failed to load statistics folder %s: %s", self._folder_path, exc)
            self._sample_pairs = []
            self._normalization_available = False
            self.clear_results()
            self.state_changed.emit()
            self.app_view_model.set_status_message(f"Failed to load statistics folder: {exc}")
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
                f"Loaded statistics folder with {len(sample_pairs)} samples"
            )
        else:
            self.app_view_model.set_status_message(
                "Loaded statistics folder with "
                f"{len(sample_pairs)} samples; area normalization disabled because at least one sample has no area CSV"
            )

    def run_statistics(self) -> None:
        if self._running:
            return
        if self._folder_path is None:
            self.app_view_model.set_status_message("Set a workspace folder first.")
            return
        if not self._sample_pairs:
            self.app_view_model.set_status_message("No valid sample pairs were found in this folder.")
            return

        worker = StatisticsWorker(
            folder_path=self._folder_path,
            normalize_by_area=self._normalize_by_area,
            fit_window_hours=self._fit_window_hours,
            area_filter_size=self._area_filter_size,
        )
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

    def _on_statistics_finished(self, success: bool, result: object, message: str) -> None:
        self._running = False
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if not success:
            logger.error("Statistics processing failed: %s", message)
            self.app_view_model.set_status_message(message)
            return

        self._results_df, self._traces_by_sample, self._saved_csv_paths = result
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

    def result_row_for_cell(self, fov: int, cell: int) -> dict[str, float | bool | str] | None:
        sample_results = self._sample_results()
        if sample_results is None:
            return None
        row_df = sample_results[
            (sample_results["fov"] == fov) & (sample_results["cell"] == cell)
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

    def _current_sample_fov_groups(self) -> dict[int, list[tuple[int, int]]]:
        sample_results = self._sample_results()
        groups: dict[int, list[tuple[int, int]]] = {}
        if sample_results is None or sample_results.empty:
            return groups
        for _, row in sample_results.iterrows():
            fov = int(row["fov"])
            cell = int(row["cell"])
            groups.setdefault(fov, []).append((fov, cell))
        for fov in groups:
            groups[fov].sort(key=lambda value: value[1])
        return groups

    def _preferred_metric(self) -> str | None:
        metrics = [value for _label, value in self.metric_options]
        if "auc" in metrics:
            return "auc"
        if "onset_time" in metrics:
            return "onset_time"
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
