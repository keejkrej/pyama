"""Consolidated view for the modeling tab."""

import logging
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyama.tasks import analyze_fitting_quality, get_model
from pyama.types import FitParam, FitParams
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.constants import DEFAULT_DIR
from pyama_gui.modeling.view_model import ModelingViewModel
from pyama_gui.types.modeling import FittingRequest
from pyama_gui.widgets import MplCanvas

logger = logging.getLogger(__name__)


class ModelingView(QWidget):
    """Consolidated modeling tab view."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = ModelingViewModel(app_view_model, self)
        self._parameter_model_type: str | None = None
        self._selected_fit_cell: tuple[int, int] | None = None
        self._fit_page = 0
        self._parameter_names: list[str] = []
        self._parameter_display_names: dict[str, str] = {}
        self._selected_parameter: str | None = None
        self._x_parameter: str | None = None
        self._y_parameter: str | None = None
        self._build_ui()
        self._connect_signals()
        self._refresh_state()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_data_section(), 1)
        layout.addWidget(self._build_quality_section(), 1)
        layout.addWidget(self._build_parameter_section(), 1)

    def _build_data_section(self) -> QGroupBox:
        group = QGroupBox("Modeling")
        layout = QVBoxLayout(group)

        data_group = QGroupBox("Data Visualization")
        data_layout = QVBoxLayout(data_group)
        self._load_button = QPushButton("Load CSV")
        data_layout.addWidget(self._load_button)
        self._canvas = MplCanvas(self)
        data_layout.addWidget(self._canvas)
        layout.addWidget(data_group)

        fitting_group = QGroupBox("Fitting")
        fitting_layout = QVBoxLayout(fitting_group)

        form = QFormLayout()
        self._model_combo = QComboBox()
        form.addRow("Model:", self._model_combo)
        fitting_layout.addLayout(form)

        self._param_table = QTableWidget()
        self._param_table.setColumnCount(5)
        self._param_table.setHorizontalHeaderLabels(
            ["Parameter", "Name", "Value", "Min", "Max"]
        )
        self._param_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._param_table.verticalHeader().setVisible(False)
        self._param_table.setAlternatingRowColors(True)
        fitting_layout.addWidget(self._param_table)

        self._load_fitted_results_button = QPushButton("Load Fitted Results")
        fitting_layout.addWidget(self._load_fitted_results_button)
        self._start_button = QPushButton("Start Fitting")
        fitting_layout.addWidget(self._start_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        fitting_layout.addWidget(self._progress_bar)

        layout.addWidget(fitting_group)
        return group

    def _build_quality_section(self) -> QGroupBox:
        group = QGroupBox("Fitted Traces")
        layout = QVBoxLayout(group)

        self._quality_canvas = MplCanvas(self)
        layout.addWidget(self._quality_canvas)

        self._quality_stats_label = QLabel("Good: 0%, Mid: 0%, Bad: 0%")
        self._quality_stats_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self._quality_stats_label)

        self._quality_list = QListWidget()
        self._quality_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._quality_list)

        pagination_row = QHBoxLayout()
        self._quality_page_label = QLabel("Page 1 of 1")
        self._quality_prev_button = QPushButton("Previous")
        self._quality_next_button = QPushButton("Next")
        pagination_row.addWidget(self._quality_page_label)
        pagination_row.addWidget(self._quality_prev_button)
        pagination_row.addWidget(self._quality_next_button)
        layout.addLayout(pagination_row)

        return group

    def _build_parameter_section(self) -> QGroupBox:
        group = QGroupBox("Parameter Analysis")
        layout = QVBoxLayout(group)

        top_controls = QHBoxLayout()
        self._filter_checkbox = QCheckBox("Good fits only (R² > 0.9)")
        top_controls.addWidget(self._filter_checkbox)
        layout.addLayout(top_controls)

        hist_controls = QHBoxLayout()
        hist_controls.addWidget(QLabel("Single Parameter:"))
        self._param_combo = QComboBox()
        hist_controls.addWidget(self._param_combo)
        layout.addLayout(hist_controls)

        self._param_canvas = MplCanvas(self)
        layout.addWidget(self._param_canvas)

        hist_save_layout = QHBoxLayout()
        self._hist_save_button = QPushButton("Save Histogram")
        hist_save_layout.addWidget(self._hist_save_button)
        layout.addLayout(hist_save_layout)

        scatter_controls = QHBoxLayout()
        scatter_controls.addWidget(QLabel("Double Parameter:"))
        self._x_param_combo = QComboBox()
        self._y_param_combo = QComboBox()
        scatter_controls.addWidget(self._x_param_combo)
        scatter_controls.addWidget(self._y_param_combo)
        layout.addLayout(scatter_controls)

        self._scatter_canvas = MplCanvas(self)
        layout.addWidget(self._scatter_canvas)

        scatter_save_layout = QHBoxLayout()
        self._scatter_save_button = QPushButton("Save Scatter Plot")
        scatter_save_layout.addWidget(self._scatter_save_button)
        layout.addLayout(scatter_save_layout)

        return group

    def _connect_signals(self) -> None:
        self.view_model.state_changed.connect(self._refresh_state)
        self.view_model.raw_data_changed.connect(self._on_raw_data_changed)
        self.view_model.results_changed.connect(self._on_results_changed)

        self._load_button.clicked.connect(self._on_load_clicked)
        self._load_fitted_results_button.clicked.connect(
            self._on_load_fitted_results_clicked
        )
        self._start_button.clicked.connect(self._on_start_clicked)
        self._model_combo.currentTextChanged.connect(self.view_model.set_model_type)
        self._quality_list.itemClicked.connect(self._on_quality_item_clicked)
        self._quality_prev_button.clicked.connect(self._on_quality_prev_page)
        self._quality_next_button.clicked.connect(self._on_quality_next_page)
        self._filter_checkbox.stateChanged.connect(self._on_filter_changed)
        self._param_combo.currentTextChanged.connect(self._on_param_changed)
        self._x_param_combo.currentTextChanged.connect(self._on_x_param_changed)
        self._y_param_combo.currentTextChanged.connect(self._on_y_param_changed)
        self._hist_save_button.clicked.connect(self._on_hist_save_clicked)
        self._scatter_save_button.clicked.connect(self._on_scatter_save_clicked)

    @Slot()
    def _refresh_state(self) -> None:
        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(self.view_model.model_names)
        if self.view_model.model_type in self.view_model.model_names:
            self._model_combo.setCurrentText(self.view_model.model_type)
        self._model_combo.blockSignals(False)

        if (
            self._parameter_model_type != self.view_model.model_type
            or self._param_table.rowCount() == 0
        ):
            self._populate_parameter_table(self.view_model.parameter_defaults)
            self._parameter_model_type = self.view_model.model_type

        self._start_button.setEnabled(not self.view_model.running)
        if self.view_model.running:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

    @Slot(object)
    def _on_raw_data_changed(self, df: pd.DataFrame) -> None:
        self._render_raw_data_plot(df)
        if self._selected_fit_cell is not None:
            self._update_quality_plot()

    @Slot(object)
    def _on_results_changed(self, df: pd.DataFrame) -> None:
        if df is None or df.empty:
            self._clear_quality_section()
            self._clear_parameter_section()
            return
        self._update_quality_results(df)
        self._update_parameter_results(df)

    @Slot()
    def _on_load_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            str(DEFAULT_DIR),
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.view_model.load_csv(Path(file_path))

    @Slot()
    def _on_load_fitted_results_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Fitted Results CSV",
            str(DEFAULT_DIR),
            "CSV Files (*.csv);;Fitted Results (*_fitted_*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self.view_model.load_fitted_results(Path(file_path))

    @Slot()
    def _on_start_clicked(self) -> None:
        request = FittingRequest(
            model_type=self.view_model.model_type,
            model_params=self._collect_model_params(),
            model_bounds=self._collect_model_bounds(),
        )
        self.view_model.start_fitting(request)

    def _render_raw_data_plot(self, data: pd.DataFrame | None) -> None:
        if data is None or data.empty:
            self._canvas.clear()
            return

        lines_data = []
        styles_data = []
        grouped_cells = list(data.groupby(level=[0, 1], sort=False))
        for _, cell_data in grouped_cells:
            cell_data = cell_data.sort_values("time")
            lines_data.append(
                (cell_data["time"].to_numpy(), cell_data["value"].to_numpy())
            )
            styles_data.append({"color": "gray", "alpha": 0.2, "linewidth": 0.5})
        if grouped_cells:
            mean_by_time = data.groupby("time", sort=True)["value"].mean()
            lines_data.append((mean_by_time.index.to_numpy(), mean_by_time.to_numpy()))
            styles_data.append(
                {
                    "color": "red",
                    "linewidth": 2,
                    "label": f"Mean of {len(grouped_cells)} traces",
                }
            )
        self._canvas.plot_lines(
            lines_data,
            styles_data,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _update_quality_results(self, df: pd.DataFrame) -> None:
        self._fit_page = 0
        self._selected_fit_cell = None
        self._update_quality_statistics(df)
        self._update_quality_pagination(df)
        self._populate_quality_table(df)
        visible_ids = self._visible_fit_ids(df)
        if visible_ids:
            self._selected_fit_cell = visible_ids[0]
            self._update_quality_plot()

    def _update_quality_statistics(self, df: pd.DataFrame) -> None:
        if "r_squared" not in df.columns:
            self._quality_stats_label.setText("Good: 0%, Mid: 0%, Bad: 0%")
            return
        quality_metrics = analyze_fitting_quality(df)
        if not quality_metrics:
            self._quality_stats_label.setText("Good: 0%, Mid: 0%, Bad: 0%")
            return
        self._quality_stats_label.setText(
            "Good: "
            f"{quality_metrics['good_percentage']:.1f}%, "
            f"Mid: {quality_metrics['fair_percentage']:.1f}%, "
            f"Bad: {quality_metrics['poor_percentage']:.1f}%"
        )

    def _fov_groups(self, df: pd.DataFrame) -> dict[int, list[tuple[int, int]]]:
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

    def _update_quality_pagination(self, df: pd.DataFrame) -> None:
        fov_list = sorted(self._fov_groups(df))
        total_pages = max(1, len(fov_list))
        if self._fit_page < len(fov_list):
            current_fov = fov_list[self._fit_page]
            cell_count = len(self._fov_groups(df).get(current_fov, []))
            self._quality_page_label.setText(
                f"FOV {current_fov} ({cell_count} cells) - "
                f"Page {self._fit_page + 1} of {total_pages}"
            )
        else:
            self._quality_page_label.setText(f"Page {self._fit_page + 1} of {total_pages}")
        self._quality_prev_button.setEnabled(self._fit_page > 0)
        self._quality_next_button.setEnabled(self._fit_page < total_pages - 1)

    def _populate_quality_table(self, df: pd.DataFrame) -> None:
        trace_ids = self._visible_fit_ids(df)
        self._quality_list.blockSignals(True)
        self._quality_list.clear()
        for fov, cell in trace_ids:
            item = QListWidgetItem(f"Cell {cell}")
            item.setData(Qt.ItemDataRole.UserRole, (fov, cell))
            row = df[(df["fov"] == fov) & (df["cell"] == cell)]
            if not row.empty and "r_squared" in row.columns:
                value = row.iloc[0]["r_squared"]
                if pd.notna(value):
                    if value > 0.9:
                        item.setForeground(QColor("green"))
                    elif value > 0.7:
                        item.setForeground(QColor("orange"))
                    else:
                        item.setForeground(QColor("red"))
            self._quality_list.addItem(item)
        self._quality_list.blockSignals(False)

    def _update_quality_plot(self) -> None:
        df = self.view_model.results_df
        raw_data = self.view_model.raw_data
        cell_id = self._selected_fit_cell
        if df is None or raw_data is None or cell_id is None:
            self._quality_canvas.clear()
            return
        fov, cell = cell_id
        try:
            cell_data = raw_data.loc[(fov, cell)]
        except KeyError:
            self._quality_canvas.clear()
            return

        time_data = cell_data["time"].values
        trace_data = cell_data["value"].values
        lines_data = [(time_data, trace_data)]
        styles_data = [
            {"color": "blue", "alpha": 0.7, "label": f"FOV {fov}, Cell {cell}", "linewidth": 1}
        ]
        result_row = df[(df["fov"] == fov) & (df["cell"] == cell)]
        if not result_row.empty:
            row = result_row.iloc[0]
            model_type = row.get("model_type")
            success = row.get("success")
            r_squared = row.get("r_squared")
            if model_type and success:
                special_cols = {"fov", "cell", "model_type", "success", "r_squared"}
                fitted_params = {
                    col: row[col]
                    for col in row.index
                    if col not in special_cols and pd.notna(row[col])
                }
                try:
                    model = get_model(model_type)
                    fit_params: FitParams = {}
                    for param_name, param_value in fitted_params.items():
                        if param_name in model.DEFAULT_FIT:
                            default_param = model.DEFAULT_FIT[param_name]
                            fit_params[param_name] = FitParam(
                                name=default_param.name,
                                value=float(param_value),
                                lb=default_param.lb,
                                ub=default_param.ub,
                            )
                    fitted_trace = model.eval(time_data, model.DEFAULT_FIXED, fit_params)
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
        self._quality_canvas.plot_lines(
            lines_data,
            styles_data,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _update_parameter_results(self, df: pd.DataFrame) -> None:
        self._parameter_names = self._discover_numeric_parameters(df)
        self._parameter_display_names = self._get_parameter_display_names(df)

        self._param_combo.blockSignals(True)
        self._param_combo.clear()
        for param_key in self._parameter_names:
            self._param_combo.addItem(
                self._parameter_display_names.get(param_key, param_key),
                param_key,
            )
        self._param_combo.blockSignals(False)

        self._x_param_combo.blockSignals(True)
        self._y_param_combo.blockSignals(True)
        self._x_param_combo.clear()
        self._y_param_combo.clear()
        for param_key in self._parameter_names:
            label = self._parameter_display_names.get(param_key, param_key)
            self._x_param_combo.addItem(label, param_key)
            self._y_param_combo.addItem(label, param_key)
        self._x_param_combo.blockSignals(False)
        self._y_param_combo.blockSignals(False)

        self._selected_parameter = self._parameter_names[0] if self._parameter_names else None
        self._x_parameter = self._parameter_names[0] if self._parameter_names else None
        self._y_parameter = (
            self._parameter_names[1]
            if len(self._parameter_names) > 1
            else self._parameter_names[0]
            if self._parameter_names
            else None
        )

        if self._selected_parameter is not None:
            self._param_combo.setCurrentIndex(0)
        if self._x_parameter is not None:
            self._x_param_combo.setCurrentIndex(0)
        if self._y_parameter is not None and self._y_parameter in self._parameter_names:
            self._y_param_combo.setCurrentIndex(self._parameter_names.index(self._y_parameter))

        self._update_histogram()
        self._update_scatter_plot()

    def _clear_quality_section(self) -> None:
        self._selected_fit_cell = None
        self._fit_page = 0
        self._quality_canvas.clear()
        self._quality_list.clear()
        self._quality_stats_label.setText("Good: 0%, Mid: 0%, Bad: 0%")
        self._quality_page_label.setText("Page 1 of 1")

    def _clear_parameter_section(self) -> None:
        self._parameter_names = []
        self._parameter_display_names = {}
        self._selected_parameter = None
        self._x_parameter = None
        self._y_parameter = None
        self._param_canvas.clear()
        self._scatter_canvas.clear()
        self._param_combo.clear()
        self._x_param_combo.clear()
        self._y_param_combo.clear()

    @Slot(QListWidgetItem)
    def _on_quality_item_clicked(self, item: QListWidgetItem) -> None:
        cell_id = item.data(Qt.ItemDataRole.UserRole)
        if cell_id:
            self._selected_fit_cell = tuple(cell_id)
            self._update_quality_plot()

    @Slot()
    def _on_quality_prev_page(self) -> None:
        if self._fit_page <= 0 or self.view_model.results_df is None:
            return
        self._fit_page -= 1
        self._update_quality_pagination(self.view_model.results_df)
        self._populate_quality_table(self.view_model.results_df)
        visible_ids = self._visible_fit_ids(self.view_model.results_df)
        self._selected_fit_cell = visible_ids[0] if visible_ids else None
        self._update_quality_plot()

    @Slot()
    def _on_quality_next_page(self) -> None:
        if self.view_model.results_df is None:
            return
        total_pages = max(1, len(self._fov_groups(self.view_model.results_df)))
        if self._fit_page >= total_pages - 1:
            return
        self._fit_page += 1
        self._update_quality_pagination(self.view_model.results_df)
        self._populate_quality_table(self.view_model.results_df)
        visible_ids = self._visible_fit_ids(self.view_model.results_df)
        self._selected_fit_cell = visible_ids[0] if visible_ids else None
        self._update_quality_plot()

    @Slot()
    def _on_filter_changed(self) -> None:
        self._update_histogram()
        self._update_scatter_plot()

    @Slot(str)
    def _on_param_changed(self, _: str) -> None:
        self._selected_parameter = self._combo_data(self._param_combo)
        self._update_histogram()

    @Slot(str)
    def _on_x_param_changed(self, _: str) -> None:
        self._x_parameter = self._combo_data(self._x_param_combo)
        self._update_scatter_plot()

    @Slot(str)
    def _on_y_param_changed(self, _: str) -> None:
        self._y_parameter = self._combo_data(self._y_param_combo)
        self._update_scatter_plot()

    def _update_histogram(self) -> None:
        df = self.view_model.results_df
        if df is None or not self._selected_parameter:
            self._param_canvas.clear()
            return
        series = self._get_histogram_series(df, self._selected_parameter)
        if series is None or series.empty:
            self._param_canvas.clear()
            return
        self._param_canvas.plot_histogram(
            series.tolist(),
            bins=30,
            x_label=self._selected_parameter,
            y_label="Frequency",
        )
        mean_val = series.mean()
        std_val = series.std()
        self._param_canvas._axes.text(
            1.0,
            1.0,
            f"Mean: {mean_val:.3f}\nStd: {std_val:.3f}",
            transform=self._param_canvas._axes.transAxes,
            fontsize=10,
            verticalalignment="top",
            horizontalalignment="right",
            bbox=dict(
                boxstyle="round",
                facecolor="white",
                alpha=0.9,
                edgecolor="black",
                linewidth=1,
            ),
        )
        self._param_canvas.draw_idle()

    def _update_scatter_plot(self) -> None:
        df = self.view_model.results_df
        if (
            df is None
            or not self._x_parameter
            or not self._y_parameter
            or self._x_parameter not in df.columns
            or self._y_parameter not in df.columns
        ):
            self._scatter_canvas.clear()
            return
        x_data = pd.to_numeric(df[self._x_parameter], errors="coerce")
        y_data = pd.to_numeric(df[self._y_parameter], errors="coerce")
        if self._filter_checkbox.isChecked() and "r_squared" in df.columns:
            mask = pd.to_numeric(df["r_squared"], errors="coerce") > 0.9
            x_data = x_data[mask]
            y_data = y_data[mask]
        valid_mask = ~(x_data.isna() | y_data.isna())
        x_values = x_data[valid_mask].tolist()
        y_values = y_data[valid_mask].tolist()
        if not x_values or not y_values:
            self._scatter_canvas.clear()
            return
        self._scatter_canvas.plot_lines(
            [(x_values, y_values)],
            [{"plot_style": "scatter", "alpha": 0.6, "s": 20}],
            x_label=self._x_parameter,
            y_label=self._y_parameter,
        )

    @Slot()
    def _on_hist_save_clicked(self) -> None:
        if not self._selected_parameter:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Histogram",
            str(Path(DEFAULT_DIR) / f"{self._selected_parameter}.png"),
            "PNG Files (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._update_histogram()
            self._param_canvas.figure.savefig(file_path, dpi=300, bbox_inches="tight")
            path = Path(file_path)
            self.app_view_model.set_status_message(f"{path.name} saved to {path.parent}")

    @Slot()
    def _on_scatter_save_clicked(self) -> None:
        if not self._x_parameter or not self._y_parameter:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Scatter Plot",
            str(Path(DEFAULT_DIR) / f"{self._x_parameter}_vs_{self._y_parameter}.png"),
            "PNG Files (*.png)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._update_scatter_plot()
            self._scatter_canvas.figure.savefig(file_path, dpi=300, bbox_inches="tight")
            path = Path(file_path)
            self.app_view_model.set_status_message(f"{path.name} saved to {path.parent}")

    def _populate_parameter_table(
        self, params_dict: dict[str, dict[str, object]]
    ) -> None:
        self._param_table.blockSignals(True)
        try:
            param_names = list(params_dict)
            self._param_table.clearContents()
            self._param_table.setRowCount(len(param_names))
            for row, param_name in enumerate(param_names):
                values = params_dict[param_name]
                self._set_param_item(row, 0, param_name, editable=False)
                self._set_param_item(row, 1, values.get("name"), editable=False)
                self._set_param_item(row, 2, values.get("value"))
                self._set_param_item(row, 3, values.get("min"))
                self._set_param_item(row, 4, values.get("max"))
        finally:
            self._param_table.blockSignals(False)

    def _collect_model_params(self) -> dict[str, float]:
        values_dict = self._read_parameter_table()
        return {
            param_name: float(fields["value"])
            for param_name, fields in values_dict.items()
            if "value" in fields and fields.get("value") is not None
        }

    def _collect_model_bounds(self) -> dict[str, tuple[float, float]]:
        values_dict = self._read_parameter_table()
        return {
            param_name: (float(fields["min"]), float(fields["max"]))
            for param_name, fields in values_dict.items()
            if fields.get("min") is not None and fields.get("max") is not None
        }

    def _read_parameter_table(self) -> dict[str, dict[str, object]]:
        values: dict[str, dict[str, object]] = {}
        for row in range(self._param_table.rowCount()):
            param_item = self._param_table.item(row, 0)
            if param_item is None:
                continue
            values[param_item.text()] = {
                "name": self._item_text(row, 1),
                "value": self._coerce(self._item_text(row, 2)),
                "min": self._coerce(self._item_text(row, 3)),
                "max": self._coerce(self._item_text(row, 4)),
            }
        return values

    def _set_param_item(
        self, row: int, column: int, value: object, *, editable: bool = True
    ) -> None:
        item = QTableWidgetItem("" if value is None else str(value))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._param_table.setItem(row, column, item)

    def _item_text(self, row: int, column: int) -> str:
        item = self._param_table.item(row, column)
        return item.text().strip() if item is not None else ""

    @staticmethod
    def _coerce(value: str) -> object:
        if value == "":
            return None
        try:
            return float(value)
        except ValueError:
            return value

    @staticmethod
    def _combo_data(combo: QComboBox) -> str | None:
        value = combo.currentData()
        return None if value is None else str(value)

    def _get_histogram_series(self, df: pd.DataFrame, param_name: str) -> pd.Series | None:
        data = pd.to_numeric(df.get(param_name), errors="coerce").dropna()
        if data.empty:
            return None
        if self._filter_checkbox.isChecked() and "r_squared" in df.columns:
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
        display_names = {}
        model_type = None
        if "model_type" in df.columns and not df.empty:
            model_type = df["model_type"].iloc[0]
            if pd.isna(model_type):
                model_type = None
        if model_type:
            try:
                model = get_model(str(model_type).lower())
                for param_key, param in model.DEFAULT_FIXED.items():
                    display_names[param_key] = param.name
                for param_key, param in model.DEFAULT_FIT.items():
                    display_names[param_key] = param.name
            except (ValueError, AttributeError):
                pass
        return display_names
