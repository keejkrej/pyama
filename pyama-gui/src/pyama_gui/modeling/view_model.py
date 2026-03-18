"""View-model for the modeling tab."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from PySide6.QtCore import QObject, Signal

from pyama.tasks import FittingService, get_model, list_models, load_analysis_csv
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.task_runner import TaskWorker, WorkerHandle, run_task
from pyama_gui.types.modeling import FittingRequest

logger = logging.getLogger(__name__)


class ModelingFittingWorker(TaskWorker):
    """Run model fitting in the background."""

    def __init__(
        self,
        *,
        csv_file: Path,
        model_type: str,
        model_params: dict[str, float],
        model_bounds: dict[str, tuple[float, float]],
    ) -> None:
        super().__init__()
        self._csv_file = csv_file
        self._model_type = model_type
        self._model_params = model_params
        self._model_bounds = model_bounds

    def run(self) -> None:
        try:
            if self.cancelled:
                self.emit_failure("Fitting cancelled")
                return
            service = FittingService()
            results_df, saved_csv_path = service.fit_csv_file(
                self._csv_file,
                self._model_type,
                model_params=self._model_params,
                model_bounds=self._model_bounds,
            )
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
        self._model_type = self._model_names[0] if self._model_names else "maturation"
        self._parameter_defaults: dict[str, dict[str, Any]] = {}
        self._running = False
        self._worker_handle: WorkerHandle | None = None
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
    def parameter_defaults(self) -> dict[str, dict[str, Any]]:
        return {
            param_name: dict(values)
            for param_name, values in self._parameter_defaults.items()
        }

    @property
    def running(self) -> bool:
        return self._running

    def load_csv(self, path: Path) -> None:
        try:
            df = load_analysis_csv(path)
        except Exception as exc:
            logger.exception("Failed to load analysis CSV")
            self._raw_data = None
            self._raw_csv_path = None
            self.raw_data_changed.emit(pd.DataFrame())
            self.app_view_model.set_status_message(f"Failed to load {path.name}: {exc}")
            return

        self._raw_data = df
        self._raw_csv_path = path
        self._results_df = None
        self._saved_csv_path = None
        self.raw_data_changed.emit(df)
        self.results_changed.emit(pd.DataFrame())
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
            model_params=request.model_params,
            model_bounds=request.model_bounds,
        )
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

        results_df, saved_csv_path = result
        self._results_df = results_df
        self._saved_csv_path = saved_csv_path
        self.results_changed.emit(results_df)
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

    def _clear_worker_handle(self) -> None:
        self._worker_handle = None

    def _available_model_names(self) -> list[str]:
        try:
            return list(list_models())
        except Exception:
            return ["maturation"]

    def _update_parameter_defaults(self) -> None:
        if not self._model_type:
            self._parameter_defaults = {}
            return
        try:
            model = get_model(self._model_type)
            params_dict: dict[str, dict[str, Any]] = {}
            for param_name, fixed_param in model.DEFAULT_FIXED.items():
                params_dict[param_name] = {
                    "name": fixed_param.name,
                    "value": fixed_param.value,
                    "min": None,
                    "max": None,
                }
            for param_name, fit_param in model.DEFAULT_FIT.items():
                params_dict[param_name] = {
                    "name": fit_param.name,
                    "value": fit_param.value,
                    "min": fit_param.lb,
                    "max": fit_param.ub,
                }
        except Exception as exc:
            logger.warning("Failed to prepare parameter defaults: %s", exc)
            params_dict = {}
        self._parameter_defaults = params_dict
        self.state_changed.emit()
