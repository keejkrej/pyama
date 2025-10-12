"""Controller for analysis fitting interactions and background jobs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama_core.analysis.fitting import fit_trace_data, get_trace
from pyama_core.analysis.models import get_model, get_types, list_models
from pyama_core.io.analysis_csv import discover_csv_files, load_analysis_csv

from pyama_qt.models.analysis import AnalysisModel, FittingRequest
from pyama_qt.services import WorkerHandle, start_worker
from pyama_qt.views.analysis.view import AnalysisView

logger = logging.getLogger(__name__)


class AnalysisFittingController(QObject):
    """Handles fitting requests, QC visualization, and worker lifecycle."""

    def __init__(
        self,
        view: AnalysisView,
        model: AnalysisModel,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._view = view
        self._model = model

        self._worker: WorkerHandle | None = None
        self._current_cell: str | None = None
        self._default_params: dict[str, float] = {}
        self._default_bounds: dict[str, tuple[float, float]] = {}

        self._view.fitting_panel.set_available_models(self._available_model_names())
        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_defaults()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        fitting_panel = self._view.fitting_panel
        fitting_panel.fit_requested.connect(self._on_fit_requested)
        fitting_panel.visualize_requested.connect(self._on_visualize_requested)
        fitting_panel.shuffle_requested.connect(self._on_shuffle_requested)
        fitting_panel.model_changed.connect(self._on_model_changed)
        fitting_panel.cell_visualized.connect(self._on_cell_visualized)

    def _connect_model_signals(self) -> None:
        self._model.data_model.rawDataChanged.connect(self._handle_raw_data_changed)
        self._model.fitting_model.isFittingChanged.connect(
            self._view.fitting_panel.set_fitting_active
        )
        self._model.fitting_model.statusMessageChanged.connect(
            self._view.status_bar.showMessage
        )

    def _initialise_defaults(self) -> None:
        self._on_model_changed(self._model.fitting_model.model_type())

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_fit_requested(
        self,
        model_type: str,
        params: dict,
        bounds: dict,
        manual: bool,
    ) -> None:
        if self._model.data_model.raw_data() is None:
            self._view.status_bar.showMessage("Load a CSV file before starting fitting")
            return

        model_params = params if manual and params else self._default_params
        model_bounds = bounds if manual and bounds else self._default_bounds

        request = FittingRequest(
            model_type=model_type,
            model_params=model_params,
            model_bounds=model_bounds,
        )
        self._model.fitting_model.set_model_params(model_params)
        self._model.fitting_model.set_model_bounds(model_bounds)
        self._start_fitting(request)

    def _on_visualize_requested(self, cell_name: str) -> None:
        if not cell_name:
            return
        raw = self._model.data_model.raw_data()
        if raw is None or cell_name not in raw.columns:
            self._view.status_bar.showMessage(f"Cell '{cell_name}' not found")
            return

        cell_index = list(raw.columns).index(cell_name)
        time_data, intensity_data = get_trace(raw, cell_index)

        lines: list[tuple[np.ndarray, np.ndarray]] = [(time_data, intensity_data)]
        styles = [
            {
                "plot_style": "scatter",
                "color": "blue",
                "alpha": 0.6,
                "s": 20,
                "label": f"{cell_name} (data)",
            }
        ]

        self._append_fitted_curve(cell_index, time_data, lines, styles)

        self._view.fitting_panel.show_cell_visualization(
            cell_name=cell_name,
            lines=lines,
            styles=styles,
            title=f"Quality Control - {cell_name}",
            x_label="Time (hours)",
            y_label="Intensity",
        )
        self._current_cell = cell_name

    def _on_shuffle_requested(self) -> None:
        cell_name = self._model.data_model.get_random_cell()
        if not cell_name:
            return
        self._view.fitting_panel.set_cell_candidate(cell_name)
        self._on_visualize_requested(cell_name)

    def _on_model_changed(self, model_type: str) -> None:
        if not model_type:
            return
        self._model.fitting_model.set_model_type(model_type)
        self._update_parameter_defaults(model_type)

    def _on_cell_visualized(self, cell_id: str) -> None:
        self._model.data_model.highlight_cell(cell_id)

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_raw_data_changed(self, _: pd.DataFrame) -> None:
        self._current_cell = None
        self._view.fitting_panel.clear_qc_view()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _start_fitting(self, request: FittingRequest) -> None:
        if self._worker is not None:
            self._view.status_bar.showMessage("A fitting job is already running")
            return

        data_path = self._model.data_model.raw_csv_path()
        if data_path is None:
            self._view.status_bar.showMessage("CSV path not available for fitting")
            return

        worker = _AnalysisWorker(data_folder=data_path, request=request)
        worker.progress_updated.connect(self._on_worker_progress)
        worker.file_processed.connect(self._on_worker_file_processed)
        worker.error_occurred.connect(self._on_worker_error)
        worker.finished.connect(self._on_worker_finished)

        handle = start_worker(
            worker,
            start_method="process_data",
            finished_callback=self._on_worker_thread_finished,
        )
        self._worker = handle
        self._model.fitting_model.set_is_fitting(True)
        self._model.fitting_model.set_status_message("Starting batch fitting…")
        self._model.fitting_model.set_error_message("")

    def _available_model_names(self) -> Sequence[str]:
        try:
            return list_models()
        except Exception:
            return ["trivial", "maturation"]

    def _update_parameter_defaults(self, model_type: str) -> None:
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            user_params = types["UserParams"]
            rows = []
            defaults: dict[str, float] = {}
            bounds: dict[str, tuple[float, float]] = {}
            for name in user_params.__annotations__.keys():
                default_val = getattr(model.DEFAULTS, name)
                min_val, max_val = getattr(model.BOUNDS, name)
                defaults[name] = float(default_val)
                bounds[name] = (float(min_val), float(max_val))
                rows.append(
                    {
                        "name": name,
                        "value": default_val,
                        "min": min_val,
                        "max": max_val,
                    }
                )
            df = pd.DataFrame(rows).set_index("name") if rows else pd.DataFrame()
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            df = pd.DataFrame()
            defaults = {}
            bounds = {}

        self._default_params = defaults
        self._default_bounds = bounds
        self._view.fitting_panel.set_parameter_defaults(df)
        self._model.fitting_model.set_model_params(defaults)
        self._model.fitting_model.set_model_bounds(bounds)

    def _append_fitted_curve(
        self,
        cell_index: int,
        time_data: np.ndarray,
        lines: list[tuple[np.ndarray, np.ndarray]],
        styles: list[dict],
    ) -> None:
        results = self._model.results_model.results()
        if results is None or results.empty:
            return

        cell_fit = results[results["cell_id"] == cell_index]
        if cell_fit.empty:
            return

        first_fit = cell_fit.iloc[0]
        success_val = first_fit.get("success")
        if not (
            success_val in [True, "True", "true", 1, "1"]
            or (isinstance(success_val, str) and str(success_val).lower() == "true")
        ):
            return

        model_type = str(first_fit.get("model_type", "")).lower()
        try:
            model = get_model(model_type)
            types = get_types(model_type)
            user_params = types["UserParams"]
            params_cls = types["Params"]
            param_names = list(user_params.__annotations__.keys())
            params_dict = {}
            for name in param_names:
                if name in cell_fit.columns and pd.notna(first_fit[name]):
                    params_dict[name] = float(first_fit[name])
            if len(params_dict) != len(param_names):
                return
            all_param_names = list(params_cls.__annotations__.keys())
            default_dict = {p: getattr(model.DEFAULTS, p) for p in all_param_names}
            default_dict.update(params_dict)
            params_obj = params_cls(**default_dict)
            t_smooth = np.linspace(time_data.min(), time_data.max(), 200)
            y_fit = model.eval(t_smooth, params_obj)
            r_squared = float(first_fit.get("r_squared", 0))
            lines.append((t_smooth, y_fit))
            styles.append(
                {
                    "plot_style": "line",
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Fit (R²={r_squared:.3f})",
                }
            )
        except Exception as exc:
            logger.warning(
                "Failed to add fitted curve for cell %s: %s", cell_index, exc
            )

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------
    def _on_worker_progress(self, message: str) -> None:
        self._model.fitting_model.set_status_message(message)

    def _on_worker_file_processed(self, filename: str, results: pd.DataFrame) -> None:
        logger.info("Processed analysis file %s (%d rows)", filename, len(results))
        self._model.results_model.set_results(results)
        self._model.fitting_model.set_status_message(f"Processed {filename}")

    def _on_worker_error(self, message: str) -> None:
        logger.error("Analysis worker error: %s", message)
        self._model.fitting_model.set_error_message(message)
        self._model.fitting_model.set_is_fitting(False)
        self._view.status_bar.showMessage(message)

    def _on_worker_finished(self) -> None:
        logger.info("Analysis fitting completed")
        self._model.fitting_model.set_is_fitting(False)
        self._model.fitting_model.set_status_message("Fitting complete")

        raw_csv_path = self._model.data_model.raw_csv_path()
        if raw_csv_path:
            fitted_path = raw_csv_path.parent / f"{raw_csv_path.stem}_fitted.csv"
            if fitted_path.exists():
                try:
                    self._model.results_model.load_from_csv(fitted_path)
                except Exception as exc:
                    logger.warning("Failed to load fitted results from disk: %s", exc)

    def _on_worker_thread_finished(self) -> None:
        logger.info("Analysis worker thread finished")
        self._worker = None


class _AnalysisWorker(QObject):
    """Background worker executing fitting across CSV files."""

    progress_updated = Signal(str)
    file_processed = Signal(str, object)
    finished = Signal()
    error_occurred = Signal(str)

    def __init__(self, *, data_folder: Path, request: FittingRequest) -> None:
        super().__init__()
        self._data_folder = data_folder
        self._request = request
        self._is_cancelled = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def process_data(self) -> None:
        try:
            trace_files = discover_csv_files(self._data_folder)
            if not trace_files:
                self.error_occurred.emit("No CSV files found for analysis")
                return

            self.progress_updated.emit(f"Found {len(trace_files)} file(s) for fitting")

            for idx, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    self.progress_updated.emit("Fitting cancelled")
                    break

                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({idx + 1}/{len(trace_files)})"
                )

                try:
                    df = load_analysis_csv(trace_path)
                except Exception as exc:
                    self.error_occurred.emit(f"Failed to load {trace_path.name}: {exc}")
                    continue

                n_cells = df.shape[1]
                results = []

                def progress_callback(cell_id):
                    if cell_id % 30 == 0 or cell_id == n_cells - 1:
                        logger.info(f"Fitting cell: {cell_id + 1}/{n_cells}")

                for cell_idx in range(n_cells):
                    if self._is_cancelled:
                        break

                    try:
                        fit_result = fit_trace_data(
                            df,
                            self._request.model_type,
                            cell_idx,
                            progress_callback=progress_callback,
                            bounds=self._request.model_bounds,
                            initial_params=self._request.model_params,
                        )
                        results.append(fit_result)
                    except Exception as exc:
                        logger.warning(
                            "Failed to fit cell %s in %s: %s",
                            cell_idx,
                            trace_path.name,
                            exc,
                        )
                        continue

                if results:
                    results_df = pd.DataFrame(results)
                    results_df["cell_id"] = results_df.get(
                        "cell_id", range(len(results))
                    )
                    self.file_processed.emit(trace_path.name, results_df)

        except Exception as exc:
            logger.exception("Unexpected analysis worker failure")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished.emit()
