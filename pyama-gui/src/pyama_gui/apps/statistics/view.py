"""Consolidated view for the statistics tab."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.statistics.view_model import StatisticsViewModel
from pyama_gui.widgets import MplCanvas


def _as_numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


class StatisticsView(QWidget):
    """Consolidated statistics tab view."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = StatisticsViewModel(app_view_model, self)
        self._build_ui()
        self._connect_signals()
        self._refresh_state()
        self._refresh_results()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_load_section(), 1)
        layout.addWidget(self._build_detail_section(), 1)
        layout.addWidget(self._build_comparison_section(), 1)

    def _build_load_section(self) -> QGroupBox:
        group = QGroupBox("Sample", self)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(group)

        self._sample_list = QListWidget()
        self._sample_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._sample_list.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._sample_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        layout.addWidget(self._sample_list)

        self._normalize_checkbox = QCheckBox("Normalize by area")
        normalize_row = QHBoxLayout()
        normalize_row.addWidget(self._normalize_checkbox)
        normalize_row.addStretch()
        layout.addLayout(normalize_row)

        self._interval_label = QLabel("Time interval (min):")
        self._interval_spin = QDoubleSpinBox()
        self._interval_spin.setRange(0.1, 1000.0)
        self._interval_spin.setSingleStep(0.5)
        interval_row = QHBoxLayout()
        interval_row.addWidget(self._interval_label)
        interval_row.addWidget(self._interval_spin)
        interval_row.addStretch()
        layout.addLayout(interval_row)

        self._window_label = QLabel("Onset window (min):")
        self._window_spin = QDoubleSpinBox()
        self._window_spin.setRange(1.0, 10000.0)
        self._window_spin.setSingleStep(10.0)
        window_row = QHBoxLayout()
        window_row.addWidget(self._window_label)
        window_row.addWidget(self._window_spin)
        window_row.addStretch()
        layout.addLayout(window_row)

        self._filter_label = QLabel("Area filter size:")
        self._filter_spin = QSpinBox()
        self._filter_spin.setRange(1, 101)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self._filter_label)
        filter_row.addWidget(self._filter_spin)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._run_button = QPushButton("Statistics")
        layout.addWidget(self._run_button)
        layout.setStretchFactor(self._sample_list, 1)
        return group

    def _build_detail_section(self) -> QGroupBox:
        group = QGroupBox("Trace", self)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(group)

        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample:"))
        self._detail_sample_combo = QComboBox()
        sample_row.addWidget(self._detail_sample_combo)
        layout.addLayout(sample_row)

        self._stats_label = QLabel("")
        self._stats_label.setWordWrap(True)
        layout.addWidget(self._stats_label)

        self._trace_canvas = MplCanvas(self)
        layout.addWidget(self._trace_canvas)

        self._trace_list = QListWidget()
        layout.addWidget(self._trace_list)

        pagination_row = QHBoxLayout()
        self._page_label = QLabel("Page 1 of 1")
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._prev_button)
        pagination_row.addWidget(self._next_button)
        layout.addLayout(pagination_row)
        return group

    def _build_comparison_section(self) -> QGroupBox:
        group = QGroupBox("Comparison", self)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(group)

        metric_row = QHBoxLayout()
        metric_row.addWidget(QLabel("Metric:"))
        self._metric_combo = QComboBox()
        metric_row.addWidget(self._metric_combo)
        layout.addLayout(metric_row)

        self._boxplot_canvas = MplCanvas(self)
        layout.addWidget(self._boxplot_canvas)

        self._summary_table = QTableWidget(0, 6)
        self._summary_table.setHorizontalHeaderLabels(
            ["Sample", "N", "Mean", "Std", "Median", "IQR"]
        )
        header = self._summary_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._summary_table.verticalHeader().setVisible(False)
        layout.addWidget(self._summary_table)
        return group

    def _connect_signals(self) -> None:
        self.view_model.state_changed.connect(self._refresh_state)
        self.view_model.results_changed.connect(self._refresh_results)

        self._run_button.clicked.connect(self._on_run_clicked)
        self._normalize_checkbox.toggled.connect(self._on_normalize_toggled)
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        self._window_spin.valueChanged.connect(self._on_window_changed)
        self._filter_spin.valueChanged.connect(self._on_filter_changed)
        self._detail_sample_combo.currentTextChanged.connect(self._on_sample_changed)
        self._trace_list.itemClicked.connect(self._on_trace_clicked)
        self._prev_button.clicked.connect(self.view_model.previous_detail_page)
        self._next_button.clicked.connect(self.view_model.next_detail_page)
        self._metric_combo.currentIndexChanged.connect(self._on_metric_changed)

    @Slot()
    def _refresh_state(self) -> None:
        state = self.view_model.state
        self._sample_list.clear()
        for pair in self.view_model.sample_pairs:
            self._sample_list.addItem(pair.sample_name)

        self._normalize_checkbox.blockSignals(True)
        self._normalize_checkbox.setChecked(state.normalize_by_area)
        self._normalize_checkbox.setEnabled(state.normalization_available)
        self._normalize_checkbox.blockSignals(False)

        self._interval_spin.blockSignals(True)
        self._interval_spin.setValue(state.frame_interval_minutes)
        self._interval_spin.blockSignals(False)

        self._window_spin.blockSignals(True)
        self._window_spin.setValue(state.fit_window_min)
        self._window_spin.blockSignals(False)

        self._filter_spin.blockSignals(True)
        self._filter_spin.setValue(state.area_filter_size)
        self._filter_spin.blockSignals(False)

        self._detail_sample_combo.blockSignals(True)
        self._detail_sample_combo.clear()
        self._detail_sample_combo.addItems(state.sample_names)
        if state.selected_sample in state.sample_names:
            self._detail_sample_combo.setCurrentText(state.selected_sample)
        self._detail_sample_combo.blockSignals(False)

        self._metric_combo.blockSignals(True)
        self._metric_combo.clear()
        for label, value in state.metric_options:
            self._metric_combo.addItem(label, value)
        if state.selected_metric is not None:
            index = self._metric_combo.findData(state.selected_metric)
            if index >= 0:
                self._metric_combo.setCurrentIndex(index)
        self._metric_combo.blockSignals(False)

        show_filter = state.normalization_available and state.normalize_by_area
        self._filter_label.setVisible(show_filter)
        self._filter_spin.setVisible(show_filter)
        self._filter_spin.setEnabled(show_filter and not state.running)

        self._run_button.setEnabled(not state.running)
        self._normalize_checkbox.setEnabled(
            not state.running and state.normalization_available
        )
        self._interval_spin.setEnabled(not state.running)
        self._window_spin.setEnabled(not state.running)
        self._detail_sample_combo.setEnabled(bool(state.sample_names))
        self._prev_button.setEnabled(state.detail_page.can_previous)
        self._next_button.setEnabled(state.detail_page.can_next)
        self._page_label.setText(state.detail_page.label)
        self._stats_label.setText(state.detail_stats_text)

    @Slot()
    def _refresh_results(self) -> None:
        state = self.view_model.state
        self._refresh_state()

        self._trace_list.blockSignals(True)
        self._trace_list.clear()
        for position, roi in state.visible_trace_ids:
            item = QListWidgetItem(f"ROI {roi}")
            item.setData(Qt.ItemDataRole.UserRole, (position, roi))
            color = self._row_color(position, roi)
            if color is not None:
                item.setForeground(color)
            self._trace_list.addItem(item)
        self._trace_list.blockSignals(False)

        if state.trace_plot is None:
            self._trace_canvas.clear()
        else:
            self._trace_canvas.plot_lines(
                state.trace_plot.lines_data,
                state.trace_plot.styles_data,
                title=state.trace_plot.title,
                x_label=state.trace_plot.x_label,
                y_label=state.trace_plot.y_label,
            )

        if state.comparison_plot is None:
            self._boxplot_canvas.clear()
        else:
            self._boxplot_canvas.plot_boxplot(
                state.comparison_plot.boxplot_groups,
                title=state.comparison_plot.title,
                x_label=state.comparison_plot.x_label,
                y_label=state.comparison_plot.y_label,
            )

        self._summary_table.setRowCount(len(state.summary_rows))
        for row_index, row_values in enumerate(state.summary_rows):
            for col_index, value in enumerate(row_values):
                text = f"{value:.3f}" if isinstance(value, float) else str(value)
                self._summary_table.setItem(
                    row_index, col_index, QTableWidgetItem(text)
                )

    def _row_color(self, position: int, roi: int) -> QColor | None:
        row = self.view_model.result_row_for_cell(position, roi)
        if row is None:
            return None
        success = bool(row.get("success", False))
        if not success:
            return QColor("red")
        if self.view_model.selected_metric != "onset_time_min":
            return QColor("green")
        r_squared = _as_numeric(row.get("r_squared"))
        if r_squared is None:
            return QColor("green")
        if r_squared > 0.9:
            return QColor("green")
        if r_squared > 0.7:
            return QColor("orange")
        return QColor("red")

    @Slot()
    def _on_run_clicked(self) -> None:
        self.view_model.set_normalize_by_area(self._normalize_checkbox.isChecked())
        self.view_model.set_frame_interval_minutes(float(self._interval_spin.value()))
        self.view_model.set_fit_window_min(float(self._window_spin.value()))
        self.view_model.set_area_filter_size(int(self._filter_spin.value()))
        self.view_model.run_statistics()

    @Slot()
    def _on_metric_changed(self) -> None:
        data = self._metric_combo.currentData()
        if data is not None:
            self.view_model.set_selected_metric(str(data))

    @Slot(bool)
    def _on_normalize_toggled(self, checked: bool) -> None:
        self.view_model.set_normalize_by_area(checked)

    @Slot(float)
    def _on_window_changed(self, value: float) -> None:
        self.view_model.set_fit_window_min(float(value))

    @Slot(float)
    def _on_interval_changed(self, value: float) -> None:
        self.view_model.set_frame_interval_minutes(float(value))

    @Slot(int)
    def _on_filter_changed(self, value: int) -> None:
        self.view_model.set_area_filter_size(int(value))

    @Slot(str)
    def _on_sample_changed(self, sample_name: str) -> None:
        self.view_model.set_selected_sample(sample_name)

    @Slot(QListWidgetItem)
    def _on_trace_clicked(self, item: QListWidgetItem) -> None:
        cell_id = item.data(Qt.ItemDataRole.UserRole)
        if cell_id:
            self.view_model.set_selected_cell(tuple(cell_id))
