"""Consolidated view for the modeling tab."""

import logging

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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

from pyama.apps.modeling.fitting import analyze_fitting_quality
from pyama.apps.modeling.models import get_model
from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.modeling.view_model import ModelingViewModel
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
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.1, 1000.0)
        self._interval_spin.setSingleStep(0.5)
        form.addRow("Time interval (min):", self._interval_spin)
        fitting_layout.addLayout(form)

        self._param_table = QTableWidget()
        self._param_table.setColumnCount(7)
        self._param_table.setHorizontalHeaderLabels(
            ["Parameter", "Name", "Mode", "Interest", "Value", "Min", "Max"]
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
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
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
        state = self.view_model.state

        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(state.model_names)
        if state.model_type in state.model_names:
            self._model_combo.setCurrentText(state.model_type)
        self._model_combo.blockSignals(False)

        self._interval_spin.blockSignals(True)
        self._interval_spin.setValue(state.frame_interval_minutes)
        self._interval_spin.blockSignals(False)

        if (
            self._parameter_model_type != state.model_type
            or self._param_table.rowCount() == 0
        ):
            self._populate_parameter_table(state.parameters)
            self._parameter_model_type = state.model_type

        self._start_button.setEnabled(not state.running)
        self._interval_spin.setEnabled(not state.running)
        if state.running:
            self._progress_bar.setRange(0, 0)
            self._progress_bar.show()
        else:
            self._progress_bar.hide()

        self._quality_stats_label.setText(state.quality_stats_label)
        self._quality_page_label.setText(state.quality_page.label)
        self._quality_prev_button.setEnabled(state.quality_page.can_previous)
        self._quality_next_button.setEnabled(state.quality_page.can_next)
        self._render_quality_rows(state.quality_rows)
        self._render_plot(self._canvas, state.raw_plot)
        self._render_plot(self._quality_canvas, state.quality_plot)
        self._render_histogram(state.histogram_plot)
        self._render_plot(self._scatter_canvas, state.scatter_plot)
        self._sync_parameter_combos(state)
        self._hist_save_button.setEnabled(state.can_save_histogram)
        self._scatter_save_button.setEnabled(state.can_save_scatter)

    @Slot(object)
    def _on_raw_data_changed(self, df: pd.DataFrame) -> None:
        self._refresh_state()

    @Slot(object)
    def _on_results_changed(self, df: pd.DataFrame) -> None:
        self._refresh_state()

    @Slot()
    def _on_load_clicked(self) -> None:
        self.view_model.request_load_csv()

    @Slot()
    def _on_load_fitted_results_clicked(self) -> None:
        self.view_model.request_load_fitted_results()

    @Slot()
    def _on_start_clicked(self) -> None:
        request = self.view_model.build_fitting_request(self._read_parameter_table())
        self.view_model.start_fitting(request)

    @Slot(float)
    def _on_interval_changed(self, value: float) -> None:
        self.view_model.set_frame_interval_minutes(float(value))

    def _render_plot(self, canvas: MplCanvas, plot_spec) -> None:
        if plot_spec is None:
            canvas.clear()
            return
        if plot_spec.kind == "histogram":
            self._render_histogram(plot_spec)
            return
        if plot_spec.kind == "boxplot":
            canvas.plot_boxplot(
                plot_spec.boxplot_groups,
                title=plot_spec.title,
                x_label=plot_spec.x_label,
                y_label=plot_spec.y_label,
            )
            return
        canvas.plot_lines(
            plot_spec.lines_data,
            plot_spec.styles_data,
            title=plot_spec.title,
            x_label=plot_spec.x_label,
            y_label=plot_spec.y_label,
        )

    def _render_histogram(self, plot_spec) -> None:
        if plot_spec is None:
            self._param_canvas.clear()
            return
        self._param_canvas.plot_histogram(
            plot_spec.histogram_data,
            bins=plot_spec.histogram_bins,
            x_label=plot_spec.x_label,
            y_label=plot_spec.y_label,
            title=plot_spec.title,
        )
        if plot_spec.annotation_text:
            self._param_canvas._axes.text(
                1.0,
                1.0,
                plot_spec.annotation_text,
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

    def _render_quality_rows(self, rows) -> None:
        self._quality_list.blockSignals(True)
        self._quality_list.clear()
        for row in rows:
            item = QListWidgetItem(row.label)
            item.setData(Qt.ItemDataRole.UserRole, row.value)
            if row.color is not None:
                item.setForeground(QColor("red" if row.selected else row.color))
            self._quality_list.addItem(item)
        self._quality_list.blockSignals(False)

    def _sync_parameter_combos(self, state) -> None:
        self._filter_checkbox.blockSignals(True)
        self._filter_checkbox.setChecked(state.filter_good_only)
        self._filter_checkbox.blockSignals(False)

        for combo, selected in (
            (self._param_combo, state.selected_parameter),
            (self._x_param_combo, state.x_parameter),
            (self._y_param_combo, state.y_parameter),
        ):
            combo.blockSignals(True)
            combo.clear()
            for label, value in state.parameter_options:
                combo.addItem(label, value)
            if selected is not None:
                index = combo.findData(selected)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _render_raw_data_plot(self, data: pd.DataFrame | None) -> None:
        if data is None or data.empty:
            self._canvas.clear()
            return

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
        self._canvas.plot_lines(
            lines_data,
            styles_data,
            x_label="Time (min)",
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

    def _position_groups(self, df: pd.DataFrame) -> dict[int, list[tuple[int, int]]]:
        groups: dict[int, list[tuple[int, int]]] = {}
        if "position" not in df.columns or "roi" not in df.columns:
            return groups
        for _, row in df.iterrows():
            groups.setdefault(int(row["position"]), []).append(
                (int(row["position"]), int(row["roi"]))
            )
        for position in groups:
            groups[position].sort(key=lambda value: value[1])
        return groups

    def _visible_fit_ids(self, df: pd.DataFrame) -> list[tuple[int, int]]:
        position_list = sorted(self._position_groups(df))
        if self._fit_page >= len(position_list):
            return []
        return self._position_groups(df).get(position_list[self._fit_page], [])

    def _update_quality_pagination(self, df: pd.DataFrame) -> None:
        position_list = sorted(self._position_groups(df))
        total_pages = max(1, len(position_list))
        if self._fit_page < len(position_list):
            current_position = position_list[self._fit_page]
            roi_count = len(self._position_groups(df).get(current_position, []))
            self._quality_page_label.setText(
                f"Position {current_position} ({roi_count} ROIs) - "
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
        for position, roi in trace_ids:
            item = QListWidgetItem(f"ROI {roi}")
            item.setData(Qt.ItemDataRole.UserRole, (position, roi))
            row = df[(df["position"] == position) & (df["roi"] == roi)]
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
        position, roi = cell_id
        try:
            cell_data = raw_data.loc[(position, roi)].sort_values("frame")
        except KeyError:
            self._quality_canvas.clear()
            return

        time_data = cell_data["time_min"].values
        trace_data = cell_data["value"].values
        lines_data = [(time_data, trace_data)]
        styles_data = [
            {
                "color": "blue",
                "alpha": 0.7,
                "label": f"Position {position}, ROI {roi}",
                "linewidth": 1,
            }
        ]
        result_row = df[(df["position"] == position) & (df["roi"] == roi)]
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
                        "Could not generate fitted curve for position %s, ROI %s: %s",
                        position,
                        roi,
                        exc,
                    )
        self._quality_canvas.plot_lines(
            lines_data,
            styles_data,
            x_label="Time (min)",
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
            self.view_model.select_fit_cell(tuple(cell_id))

    @Slot()
    def _on_quality_prev_page(self) -> None:
        self.view_model.previous_quality_page()

    @Slot()
    def _on_quality_next_page(self) -> None:
        self.view_model.next_quality_page()

    @Slot()
    def _on_filter_changed(self) -> None:
        self.view_model.set_filter_good_only(self._filter_checkbox.isChecked())

    @Slot(str)
    def _on_param_changed(self, _: str) -> None:
        data = self._combo_data(self._param_combo)
        if data is not None:
            self.view_model.set_selected_parameter(data)

    @Slot(str)
    def _on_x_param_changed(self, _: str) -> None:
        data = self._combo_data(self._x_param_combo)
        if data is not None:
            self.view_model.set_x_parameter(data)

    @Slot(str)
    def _on_y_param_changed(self, _: str) -> None:
        data = self._combo_data(self._y_param_combo)
        if data is not None:
            self.view_model.set_y_parameter(data)

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
        path = self.view_model.request_histogram_export_path()
        if path is not None:
            self._param_canvas.figure.savefig(path, dpi=300, bbox_inches="tight")
            self.view_model.notify_export_saved(path)

    @Slot()
    def _on_scatter_save_clicked(self) -> None:
        path = self.view_model.request_scatter_export_path()
        if path is not None:
            self._scatter_canvas.figure.savefig(path, dpi=300, bbox_inches="tight")
            self.view_model.notify_export_saved(path)

    def _populate_parameter_table(self, parameters) -> None:
        self._param_table.blockSignals(True)
        try:
            self._param_table.clearContents()
            self._param_table.setRowCount(len(parameters))
            for row, parameter in enumerate(parameters):
                self._set_param_item(row, 0, parameter.key, editable=False)
                self._set_param_item(row, 1, parameter.name, editable=False)
                self._set_param_item(
                    row, 2, parameter.mode.capitalize(), editable=False
                )
                self._set_param_item(
                    row, 3, "Yes" if parameter.is_interest else "No", editable=False
                )
                if parameter.preset_options:
                    combo = QComboBox(self._param_table)
                    for option in parameter.preset_options:
                        combo.addItem(option.label, option.value)
                    selected_index = 0
                    for index, option in enumerate(parameter.preset_options):
                        if option.key == parameter.selected_preset:
                            selected_index = index
                            break
                    combo.setCurrentIndex(selected_index)
                    self._param_table.setCellWidget(row, 4, combo)
                else:
                    self._param_table.removeCellWidget(row, 4)
                    self._set_param_item(row, 4, parameter.value)
                self._set_param_item(
                    row,
                    5,
                    parameter.min_value,
                    editable=parameter.mode == "fit",
                )
                self._set_param_item(
                    row,
                    6,
                    parameter.max_value,
                    editable=parameter.mode == "fit",
                )
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
            value_widget = self._param_table.cellWidget(row, 4)
            if isinstance(value_widget, QComboBox):
                value = value_widget.currentData()
            else:
                value = self._coerce(self._item_text(row, 4))
            values[param_item.text()] = {
                "name": self._item_text(row, 1),
                "value": value,
                "min": self._coerce(self._item_text(row, 5)),
                "max": self._coerce(self._item_text(row, 6)),
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
            "position",
            "roi",
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
                for param_key, param in model.get_parameters().items():
                    display_names[param_key] = param.name
            except (ValueError, AttributeError):
                pass
        return display_names
