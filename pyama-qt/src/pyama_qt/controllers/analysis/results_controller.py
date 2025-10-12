"""Controller for analysis results panel interactions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject

from pyama_qt.models.analysis import AnalysisModel
from pyama_qt.views.analysis.view import AnalysisView


class AnalysisResultsController(QObject):
    """Handles histogram, quality plot, and export interactions."""

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

        self._selected_parameter: str | None = None
        self._parameter_names: list[str] = []

        self._connect_view_signals()
        self._connect_model_signals()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------
    def _connect_view_signals(self) -> None:
        panel = self._view.results_panel
        panel.parameter_selected.connect(self._on_parameter_selected)
        panel.filter_toggled.connect(self._on_filter_toggled)
        panel.save_requested.connect(self._on_save_requested)

    def _connect_model_signals(self) -> None:
        self._model.results_model.resultsReset.connect(self._handle_results_reset)

    # ------------------------------------------------------------------
    # View → Controller handlers
    # ------------------------------------------------------------------
    def _on_parameter_selected(self, param_name: str) -> None:
        self._selected_parameter = param_name
        self._update_histogram()

    def _on_filter_toggled(self, _checked: bool) -> None:
        self._update_histogram()

    def _on_save_requested(self, folder: Path) -> None:
        df = self._model.results_model.results()
        if df is None or df.empty or not self._parameter_names:
            return

        current_param = self._selected_parameter
        for param_name in self._parameter_names:
            series = self._histogram_series(df, param_name)
            if series is None or series.empty:
                continue

            self._view.results_panel.render_histogram(
                param_name=param_name,
                values=series.tolist(),
            )
            output = folder / f"{param_name}.png"
            self._view.results_panel.export_histogram(output)

        if current_param:
            self._selected_parameter = current_param
            self._update_histogram()

    # ------------------------------------------------------------------
    # Model → Controller handlers
    # ------------------------------------------------------------------
    def _handle_results_reset(self) -> None:
        df = self._model.results_model.results()
        if df is None or df.empty:
            self._parameter_names = []
            self._selected_parameter = None
            self._view.results_panel.clear()
            return

        self._update_quality_plot(df)
        parameter_names = self._discover_numeric_parameters(df)
        self._parameter_names = parameter_names

        current = self._selected_parameter
        if current not in parameter_names:
            current = parameter_names[0] if parameter_names else None
        self._selected_parameter = current

        self._view.results_panel.set_parameter_options(
            parameter_names,
            current=current,
        )
        self._update_histogram()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_histogram(self) -> None:
        df = self._model.results_model.results()
        if df is None or df.empty or not self._selected_parameter:
            self._view.results_panel.render_histogram(
                param_name=self._selected_parameter or "",
                values=[],
            )
            return

        series = self._histogram_series(df, self._selected_parameter)
        if series is None or series.empty:
            self._view.results_panel.render_histogram(
                param_name=self._selected_parameter,
                values=[],
            )
            return

        self._view.results_panel.render_histogram(
            param_name=self._selected_parameter,
            values=series.tolist(),
        )

    def _histogram_series(self, df: pd.DataFrame, param_name: str) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None

        if "r_squared" in df.columns and self._view.results_panel.is_filter_enabled():
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            data = pd.to_numeric(df.loc[mask, param_name], errors="coerce").dropna()
            if data.empty:
                return None
        return data

    def _update_quality_plot(self, df: pd.DataFrame) -> None:
        r_squared = pd.to_numeric(df.get("r_squared"), errors="coerce").dropna()
        if r_squared.empty:
            self._view.results_panel.render_quality_plot(
                lines=[],
                styles=[],
                title="Fitting Quality",
                x_label="Cell Index",
                y_label="R²",
            )
            return

        colors = [
            "green" if r2 > 0.9 else "orange" if r2 > 0.7 else "red" for r2 in r_squared
        ]
        lines = [(list(range(len(r_squared))), r_squared.values)]
        styles = [
            {
                "plot_style": "scatter",
                "color": colors,
                "alpha": 0.6,
                "s": 20,
            }
        ]

        good_pct = (r_squared > 0.9).mean() * 100
        fair_pct = ((r_squared > 0.7) & (r_squared <= 0.9)).mean() * 100
        poor_pct = (r_squared <= 0.7).mean() * 100

        legend_text = (
            f"Good (R²>0.9): {good_pct:.1f}%\n"
            f"Fair (0.7<R²≤0.9): {fair_pct:.1f}%\n"
            f"Poor (R²≤0.7): {poor_pct:.1f}%"
        )
        self._view.results_panel.render_quality_plot(
            lines=lines,
            styles=styles,
            title="Fitting Quality",
            x_label="Cell Index",
            y_label="R²",
            legend_text=legend_text,
        )

    def _discover_numeric_parameters(self, df: pd.DataFrame) -> list[str]:
        metadata_cols = {
            "fov",
            "file",
            "cell_id",
            "model_type",
            "success",
            "residual_sum_squares",
            "message",
            "n_function_calls",
            "chisq",
            "std",
            "r_squared",
        }
        numeric_cols: list[str] = []
        for col in df.columns:
            if col in metadata_cols:
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().any():
                numeric_cols.append(col)
        return numeric_cols
