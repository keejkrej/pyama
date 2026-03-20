"""View-model for the modeling tab."""

import logging
from pathlib import Path
from typing import cast

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama.tasks import (
    ModelFitTaskRequest,
    TaskStatus,
    analyze_fitting_quality,
    get_model,
    list_models,
    load_analysis_csv,
    submit_model_fit,
)
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types.common import ListRowState, PageState, PlotSpec
from pyama_gui.types.modeling import (
    FittingRequest,
    ModelingViewState,
    ParameterEditorState,
    ParameterOptionState,
)

logger = logging.getLogger(__name__)


class ModelingFittingWorker(TaskWorker):
    """Run model fitting in the background."""

    def __init__(
        self,
        *,
        csv_file: Path,
        model_type: str,
        frame_interval_minutes: float,
        model_params: dict[str, float],
        model_bounds: dict[str, tuple[float, float]],
    ) -> None:
        super().__init__()
        self._csv_file = csv_file
        self._model_type = model_type
        self._frame_interval_minutes = frame_interval_minutes
        self._model_params = model_params
        self._model_bounds = model_bounds

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Fitting cancelled")
                return
            record = submit_model_fit(
                ModelFitTaskRequest(
                    csv_file=self._csv_file,
                    model_type=self._model_type,
                    frame_interval_minutes=self._frame_interval_minutes,
                    model_params=self._model_params,
                    model_bounds=self._model_bounds,
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
                self.emit_failure(snapshot.error_message or "Fitting failed")
                return
            results_df, saved_csv_path = snapshot.result
            self.emit_success((results_df, saved_csv_path))
        except Exception as exc:  # pragma: no cover - worker boundary
            logger.exception("Modeling fitting failed")
            self.emit_failure(str(exc))


class ModelingViewModel(QObject):
    """Tab-level state and commands for modeling."""

    state_changed = Signal()
    raw_data_changed = Signal(object)
    results_changed = Signal(object)

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self._raw_data: pd.DataFrame | None = None
        self._raw_csv_path: Path | None = None
        self._results_df: pd.DataFrame | None = None
        self._saved_csv_path: Path | None = None
        self._model_names = self._available_model_names()
        self._model_type = self._model_names[0] if self._model_names else "base"
        self._frame_interval_minutes = 10.0
        self._parameters: tuple[ParameterEditorState, ...] = ()
        self._running = False
        self._worker_handle: WorkerHandle | None = None
        self._selected_fit_cell: tuple[int, int] | None = None
        self._fit_page = 0
        self._parameter_names: list[str] = []
        self._parameter_display_names: dict[str, str] = {}
        self._selected_parameter: str | None = None
        self._x_parameter: str | None = None
        self._y_parameter: str | None = None
        self._filter_good_only = False
        self._update_parameter_defaults()

    @property
    def raw_data(self) -> pd.DataFrame | None:
        return self._raw_data

    @property
    def raw_csv_path(self) -> Path | None:
        return self._raw_csv_path

    @property
    def results_df(self) -> pd.DataFrame | None:
        return self._results_df

    @property
    def saved_csv_path(self) -> Path | None:
        return self._saved_csv_path

    @property
    def model_names(self) -> list[str]:
        return list(self._model_names)

    @property
    def model_type(self) -> str:
        return self._model_type

    @property
    def parameters(self) -> tuple[ParameterEditorState, ...]:
        return tuple(self._parameters)

    @property
    def running(self) -> bool:
        return self._running

    @property
    def state(self) -> ModelingViewState:
        return ModelingViewState(
            model_names=list(self._model_names),
            model_type=self._model_type,
            frame_interval_minutes=self._frame_interval_minutes,
            parameters=self.parameters,
            running=self._running,
            raw_plot=self.raw_plot,
            quality_plot=self.quality_plot,
            histogram_plot=self.histogram_plot,
            scatter_plot=self.scatter_plot,
            quality_rows=self.quality_rows,
            quality_stats_label=self.quality_stats_label,
            quality_page=self.quality_page,
            parameter_options=self.parameter_options,
            selected_parameter=self._selected_parameter,
            x_parameter=self._x_parameter,
            y_parameter=self._y_parameter,
            filter_good_only=self._filter_good_only,
            can_save_histogram=self.histogram_plot is not None,
            can_save_scatter=self.scatter_plot is not None,
        )

    @property
    def raw_plot(self) -> PlotSpec | None:
        data = self._raw_data
        if data is None or data.empty:
            return None
        lines_data = []
        styles_data = []
        grouped_cells = list(data.groupby(level=[0, 1], sort=False))
        for _, cell_data in grouped_cells:
            cell_data = cell_data.sort_values("frame")
            lines_data.append(
                (cell_data["time_min"].to_numpy(), cell_data["value"].to_numpy())
            )
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})
        if grouped_cells:
            mean_by_time = data.groupby("time_min", sort=True)["value"].mean()
            lines_data.append((mean_by_time.index.to_numpy(), mean_by_time.to_numpy()))
            styles_data.append(
                {
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Mean of {len(grouped_cells)} traces",
                }
            )
        return PlotSpec(
            kind="lines",
            lines_data=lines_data,
            styles_data=styles_data,
            x_label="Time (min)",
            y_label="Intensity",
        )

    @property
    def quality_rows(self) -> list[ListRowState]:
        df = self._results_df
        if df is None or df.empty:
            return []
        rows: list[ListRowState] = []
        for fov, cell in self._visible_fit_ids(df):
            color = None
            row = df[(df["fov"] == fov) & (df["cell"] == cell)]
            if not row.empty and "r_squared" in row.columns:
                value = row.iloc[0]["r_squared"]
                if pd.notna(value):
                    if value > 0.9:
                        color = "green"
                    elif value > 0.7:
                        color = "orange"
                    else:
                        color = "red"
            rows.append(
                ListRowState(
                    label=f"Cell {cell}",
                    value=(fov, cell),
                    color=color,
                    selected=(self._selected_fit_cell == (fov, cell)),
                )
            )
        return rows

    @property
    def quality_stats_label(self) -> str:
        df = self._results_df
        if df is None or df.empty or "r_squared" not in df.columns:
            return "Good: 0%, Mid: 0%, Bad: 0%"
        quality_metrics = analyze_fitting_quality(df)
        if not quality_metrics:
            return "Good: 0%, Mid: 0%, Bad: 0%"
        return (
            "Good: "
            f"{quality_metrics['good_percentage']:.1f}%, "
            f"Mid: {quality_metrics['fair_percentage']:.1f}%, "
            f"Bad: {quality_metrics['poor_percentage']:.1f}%"
        )

    @property
    def quality_page(self) -> PageState:
        df = self._results_df
        if df is None or df.empty:
            return PageState()
        fov_list = sorted(self._fov_groups(df))
        total_pages = max(1, len(fov_list))
        if self._fit_page < len(fov_list):
            current_fov = fov_list[self._fit_page]
            cell_count = len(self._fov_groups(df).get(current_fov, []))
            label = f"FOV {current_fov} ({cell_count} cells) - Page {self._fit_page + 1} of {total_pages}"
        else:
            label = f"Page {self._fit_page + 1} of {total_pages}"
        return PageState(
            label=label,
            can_previous=self._fit_page > 0,
            can_next=self._fit_page < total_pages - 1,
        )

    @property
    def quality_plot(self) -> PlotSpec | None:
        df = self._results_df
        raw_data = self._raw_data
        cell_id = self._selected_fit_cell
        if df is None or raw_data is None or cell_id is None:
            return None
        fov, cell = cell_id
        try:
            cell_data = raw_data.loc[(fov, cell)].sort_values("frame")
        except KeyError:
            return None
        time_data = cell_data["time_min"].values
        trace_data = cell_data["value"].values
        lines_data: list[tuple[object, object]] = [(time_data, trace_data)]
        styles_data: list[dict[str, object]] = [
            {
                "color": "blue",
                "alpha": 0.7,
                "label": f"FOV {fov}, Cell {cell}",
                "linewidth": 1,
            }
        ]
        result_row = df[(df["fov"] == fov) & (df["cell"] == cell)]
        if not result_row.empty:
            row = result_row.iloc[0]
            model_type = row.get("model_type")
            success = row.get("success")
            r_squared = row.get("r_squared")
            if model_type and success:
                try:
                    model = get_model(model_type)
                    fixed_params = model.get_fixed_parameters()
                    for param_name, default_param in fixed_params.items():
                        fixed_params[param_name] = default_param.clone(
                            value=float(row.get(param_name, default_param.value))
                        )
                    fit_params = model.get_fit_parameters()
                    for param_name, default_param in fit_params.items():
                        fit_params[param_name] = default_param.clone(
                            value=float(row.get(param_name, default_param.value))
                        )
                    fitted_trace = model.eval(time_data, fixed_params, fit_params)
                    label = "Fitted"
                    if pd.notna(r_squared):
                        label = f"Fitted (R²={r_squared:.3f})"
                    lines_data.append((time_data, fitted_trace))
                    styles_data.append(
                        {"color": "red", "alpha": 0.8, "label": label, "linewidth": 2}
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not generate fitted curve for FOV %s, Cell %s: %s",
                        fov,
                        cell,
                        exc,
                    )
        return PlotSpec(
            kind="lines",
            lines_data=lines_data,
            styles_data=styles_data,
            x_label="Time (min)",
            y_label="Intensity",
        )

    @property
    def parameter_options(self) -> list[tuple[str, str]]:
        return [
            (self._parameter_display_names.get(param_key, param_key), param_key)
            for param_key in self._parameter_names
        ]

    @property
    def histogram_plot(self) -> PlotSpec | None:
        df = self._results_df
        if df is None or not self._selected_parameter:
            return None
        series = self._get_histogram_series(df, self._selected_parameter)
        if series is None or series.empty:
            return None
        display_name = self._parameter_display_names.get(
            self._selected_parameter, self._selected_parameter
        )
        return PlotSpec(
            kind="histogram",
            histogram_data=series.tolist(),
            histogram_bins=30,
            x_label=display_name,
            y_label="Frequency",
            annotation_text=f"Mean: {series.mean():.3f}\nStd: {series.std():.3f}",
        )

    @property
    def scatter_plot(self) -> PlotSpec | None:
        df = self._results_df
        if (
            df is None
            or not self._x_parameter
            or not self._y_parameter
            or self._x_parameter not in df.columns
            or self._y_parameter not in df.columns
        ):
            return None
        x_data = pd.to_numeric(df[self._x_parameter], errors="coerce")
        y_data = pd.to_numeric(df[self._y_parameter], errors="coerce")
        if self._filter_good_only and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            x_data = x_data[mask]
            y_data = y_data[mask]
        valid_mask = ~(x_data.isna() | y_data.isna())
        x_values = x_data[valid_mask].tolist()
        y_values = y_data[valid_mask].tolist()
        if not x_values or not y_values:
            return None
        x_label = self._parameter_display_names.get(
            self._x_parameter, self._x_parameter
        )
        y_label = self._parameter_display_names.get(
            self._y_parameter, self._y_parameter
        )
        return PlotSpec(
            kind="lines",
            lines_data=[(x_values, y_values)],
            styles_data=[{"plot_style": "scatter", "alpha": 0.6, "s": 20}],
            x_label=x_label,
            y_label=y_label,
        )

    def request_load_csv(self) -> None:
        if self.app_view_model.dialog_service is None:
            raise RuntimeError("No dialog service configured.")
        path = self.app_view_model.dialog_service.select_open_file(
            "Select CSV File",
            str(Path.cwd()),
            "CSV Files (*.csv)",
        )
        if path is not None:
            self.load_csv(path)

    def request_load_fitted_results(self) -> None:
        if self.app_view_model.dialog_service is None:
            raise RuntimeError("No dialog service configured.")
        path = self.app_view_model.dialog_service.select_open_file(
            "Select Fitted Results CSV",
            str(Path.cwd()),
            "CSV Files (*.csv);;Fitted Results (*_fitted_*.csv)",
        )
        if path is not None:
            self.load_fitted_results(path)

    def build_fitting_request(
        self, table_values: dict[str, dict[str, object]]
    ) -> FittingRequest:
        model_params: dict[str, float] = {}
        model_bounds: dict[str, tuple[float, float]] = {}
        for param_name, fields in table_values.items():
            value = fields.get("value")
            if isinstance(value, int | float | str):
                model_params[param_name] = float(value)

            min_value = fields.get("min")
            max_value = fields.get("max")
            if isinstance(min_value, int | float | str) and isinstance(
                max_value, int | float | str
            ):
                model_bounds[param_name] = (float(min_value), float(max_value))

        return FittingRequest(
            model_type=self._model_type,
            frame_interval_minutes=self._frame_interval_minutes,
            model_params=model_params,
            model_bounds=model_bounds,
        )

    def load_csv(self, path: Path) -> None:
        try:
            df = load_analysis_csv(
                path, frame_interval_minutes=self._frame_interval_minutes
            )
        except Exception as exc:
            logger.exception("Failed to load analysis CSV")
            self._raw_data = None
            self._raw_csv_path = None
            self.raw_data_changed.emit(pd.DataFrame())
            self.app_view_model.set_status_message(f"Failed to load {path.name}: {exc}")
            self.state_changed.emit()
            return

        self._raw_data = df
        self._raw_csv_path = path
        self._results_df = None
        self._saved_csv_path = None
        self._selected_fit_cell = None
        self._fit_page = 0
        self._parameter_names = []
        self._parameter_display_names = {}
        self._selected_parameter = None
        self._x_parameter = None
        self._y_parameter = None
        self.raw_data_changed.emit(df)
        self.results_changed.emit(pd.DataFrame())
        self.state_changed.emit()
        self.app_view_model.set_status_message(f"Successfully loaded {path.name}")

    def load_fitted_results(self, path: Path) -> None:
        try:
            df = pd.read_csv(path)
        except Exception as exc:
            logger.warning("Failed to load fitted results from %s: %s", path, exc)
            self.app_view_model.set_status_message(
                f"Failed to load fitted results: {path.name}"
            )
            return

        if "model_type" in df.columns and not df.empty:
            model_type = df["model_type"].iloc[0]
            if pd.notna(model_type) and str(model_type) in self._model_names:
                self._model_type = str(model_type)
                self._update_parameter_defaults()

        self._results_df = df
        self._saved_csv_path = path
        self._refresh_results_state()
        self.state_changed.emit()
        self.results_changed.emit(df)
        self.app_view_model.set_status_message(
            f"Loaded fitted results from {path.name}"
        )

    def set_model_type(self, model_type: str) -> None:
        if not model_type or model_type == self._model_type:
            return
        self._model_type = model_type
        self._update_parameter_defaults()
        self.state_changed.emit()

    def set_frame_interval_minutes(self, value: float) -> None:
        self._frame_interval_minutes = value
        if self._raw_csv_path is not None:
            self.load_csv(self._raw_csv_path)
            return
        self.state_changed.emit()

    def start_fitting(self, request: FittingRequest) -> None:
        if self._running:
            self.app_view_model.set_status_message("A fitting job is already running.")
            return
        if self._raw_csv_path is None:
            self.app_view_model.set_status_message(
                "Load a CSV file before starting fitting."
            )
            return

        worker = ModelingFittingWorker(
            csv_file=self._raw_csv_path,
            model_type=request.model_type,
            frame_interval_minutes=request.frame_interval_minutes,
            model_params=request.model_params,
            model_bounds=request.model_bounds,
        )
        worker.progress_value.connect(self._on_worker_progress)
        worker.finished.connect(self._on_worker_finished)
        self._worker_handle = run_task(
            worker,
            start_method="run",
            finished_callback=self._clear_worker_handle,
        )
        self._running = True
        self.state_changed.emit()
        self.app_view_model.begin_busy()
        self.app_view_model.set_status_message("Fitting models...")

    def _on_worker_finished(self, success: bool, result: object, message: str) -> None:
        self._running = False
        self.state_changed.emit()
        self.app_view_model.end_busy()
        if not success:
            logger.error("Modeling fitting failed: %s", message)
            self.app_view_model.set_status_message(message)
            return

        if not (
            isinstance(result, tuple)
            and len(result) == 2
            and (isinstance(result[0], pd.DataFrame) or result[0] is None)
            and (isinstance(result[1], Path) or result[1] is None)
        ):
            self.app_view_model.set_status_message(
                "Fitting returned an invalid result."
            )
            return

        results_df, saved_csv_path = cast(
            tuple[pd.DataFrame | None, Path | None], result
        )
        self._results_df = results_df
        self._saved_csv_path = saved_csv_path
        self._refresh_results_state()
        self.results_changed.emit(results_df)
        self.state_changed.emit()
        if saved_csv_path:
            self.app_view_model.set_status_message(
                f"Fitting completed. Saved results as {saved_csv_path.name}."
            )
        elif self._raw_csv_path is not None:
            self.app_view_model.set_status_message(
                f"Fitting completed. Processed {self._raw_csv_path.name}."
            )
        else:
            self.app_view_model.set_status_message("Fitting completed successfully.")

    def _on_worker_progress(self, percent: int, message: str) -> None:
        if message:
            self.app_view_model.set_status_message(f"{message} ({percent}%)")

    def _clear_worker_handle(self) -> None:
        self._worker_handle = None

    def select_fit_cell(self, cell_id: tuple[int, int]) -> None:
        if self._selected_fit_cell == cell_id:
            return
        self._selected_fit_cell = cell_id
        self.state_changed.emit()

    def previous_quality_page(self) -> None:
        if self._fit_page <= 0 or self._results_df is None:
            return
        self._fit_page -= 1
        visible_ids = self._visible_fit_ids(self._results_df)
        self._selected_fit_cell = visible_ids[0] if visible_ids else None
        self.state_changed.emit()

    def next_quality_page(self) -> None:
        if self._results_df is None:
            return
        total_pages = max(1, len(self._fov_groups(self._results_df)))
        if self._fit_page >= total_pages - 1:
            return
        self._fit_page += 1
        visible_ids = self._visible_fit_ids(self._results_df)
        self._selected_fit_cell = visible_ids[0] if visible_ids else None
        self.state_changed.emit()

    def set_filter_good_only(self, enabled: bool) -> None:
        self._filter_good_only = enabled
        self.state_changed.emit()

    def set_selected_parameter(self, parameter_name: str) -> None:
        if not parameter_name or parameter_name == self._selected_parameter:
            return
        self._selected_parameter = parameter_name
        self.state_changed.emit()

    def set_x_parameter(self, parameter_name: str) -> None:
        if not parameter_name or parameter_name == self._x_parameter:
            return
        self._x_parameter = parameter_name
        self.state_changed.emit()

    def set_y_parameter(self, parameter_name: str) -> None:
        if not parameter_name or parameter_name == self._y_parameter:
            return
        self._y_parameter = parameter_name
        self.state_changed.emit()

    def request_histogram_export_path(self) -> Path | None:
        if (
            self._selected_parameter is None
            or self.app_view_model.dialog_service is None
        ):
            return None
        return self.app_view_model.dialog_service.select_save_file(
            "Save Histogram",
            str(Path.cwd() / f"{self._selected_parameter}.png"),
            "PNG Files (*.png)",
        )

    def request_scatter_export_path(self) -> Path | None:
        if (
            self._x_parameter is None
            or self._y_parameter is None
            or self.app_view_model.dialog_service is None
        ):
            return None
        return self.app_view_model.dialog_service.select_save_file(
            "Save Scatter Plot",
            str(Path.cwd() / f"{self._x_parameter}_vs_{self._y_parameter}.png"),
            "PNG Files (*.png)",
        )

    def notify_export_saved(self, path: Path) -> None:
        self.app_view_model.set_status_message(f"{path.name} saved to {path.parent}")

    def _refresh_results_state(self) -> None:
        df = self._results_df
        if df is None or df.empty:
            self._selected_fit_cell = None
            self._fit_page = 0
            self._parameter_names = []
            self._parameter_display_names = {}
            self._selected_parameter = None
            self._x_parameter = None
            self._y_parameter = None
            return

        self._fit_page = 0
        visible_ids = self._visible_fit_ids(df)
        self._selected_fit_cell = visible_ids[0] if visible_ids else None
        self._parameter_display_names = self._get_parameter_display_names(df)
        self._parameter_names = self._discover_interest_parameters(df)
        self._selected_parameter = (
            self._parameter_names[0] if self._parameter_names else None
        )
        self._x_parameter = self._parameter_names[0] if self._parameter_names else None
        self._y_parameter = (
            self._parameter_names[1]
            if len(self._parameter_names) > 1
            else self._parameter_names[0]
            if self._parameter_names
            else None
        )

    @staticmethod
    def _fov_groups(df: pd.DataFrame) -> dict[int, list[tuple[int, int]]]:
        groups: dict[int, list[tuple[int, int]]] = {}
        if "fov" not in df.columns or "cell" not in df.columns:
            return groups
        for _, row in df.iterrows():
            groups.setdefault(int(row["fov"]), []).append(
                (int(row["fov"]), int(row["cell"]))
            )
        for fov in groups:
            groups[fov].sort(key=lambda value: value[1])
        return groups

    def _visible_fit_ids(self, df: pd.DataFrame) -> list[tuple[int, int]]:
        fov_list = sorted(self._fov_groups(df))
        if self._fit_page >= len(fov_list):
            return []
        return self._fov_groups(df).get(fov_list[self._fit_page], [])

    def _get_histogram_series(
        self, df: pd.DataFrame, param_name: str
    ) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None
        if self._filter_good_only and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()
        return data if not data.empty else None

    @staticmethod
    def _discover_numeric_parameters(df: pd.DataFrame) -> list[str]:
        metadata_cols = {
            "fov",
            "cell",
            "file",
            "model_type",
            "success",
            "residual_sum_squares",
            "message",
            "n_function_calls",
            "chisq",
            "std",
            "r_squared",
        }
        return [
            col
            for col in df.columns
            if col not in metadata_cols
            and pd.to_numeric(df[col], errors="coerce").notna().any()
        ]

    @staticmethod
    def _get_parameter_display_names(df: pd.DataFrame) -> dict[str, str]:
        display_names: dict[str, str] = {}
        model_type = None
        if "model_type" in df.columns and not df.empty:
            model_type = df["model_type"].iloc[0]
            if pd.isna(model_type):
                model_type = None
        if model_type:
            try:
                model = get_model(str(model_type).lower())
                for param_key, param in model.get_parameters().items():
                    display_names[param_key] = param.name
            except (ValueError, AttributeError):
                pass
        return display_names

    @staticmethod
    def _discover_interest_parameters(df: pd.DataFrame) -> list[str]:
        if "model_type" not in df.columns or df.empty:
            return []
        model_type = df["model_type"].iloc[0]
        if pd.isna(model_type):
            return []
        try:
            model = get_model(str(model_type).lower())
        except (ValueError, AttributeError):
            return []
        return [
            key
            for key, param in model.get_parameters().items()
            if param.is_interest
            and key in df.columns
            and pd.to_numeric(df[key], errors="coerce").notna().any()
        ]

    def _available_model_names(self) -> list[str]:
        try:
            return list(list_models())
        except Exception:
            return ["base"]

    def _update_parameter_defaults(self) -> None:
        if not self._model_type:
            self._parameters = ()
            return
        try:
            model = get_model(self._model_type)
            parameters = []
            for param_name, param in model.get_parameters().items():
                preset_options = tuple(
                    ParameterOptionState(
                        key=preset.key,
                        label=preset.name,
                        value=preset.value,
                    )
                    for preset in param.presets
                )
                parameters.append(
                    ParameterEditorState(
                        key=param_name,
                        name=param.name,
                        mode=param.mode,
                        is_interest=param.is_interest,
                        value=param.value,
                        min_value=param.lb,
                        max_value=param.ub,
                        preset_options=preset_options,
                        selected_preset=(
                            preset_options[0].key if preset_options else None
                        ),
                    )
                )
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            parameters = []
        self._parameters = tuple(parameters)
        self.state_changed.emit()
