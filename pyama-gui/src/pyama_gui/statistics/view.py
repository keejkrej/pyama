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
from pyama_gui.statistics.view_model import StatisticsViewModel
from pyama_gui.widgets import MplCanvas


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
        group = QGroupBox("Control", self)
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

        self._window_label = QLabel("Onset window (h):")
        self._window_spin = QDoubleSpinBox()
        self._window_spin.setRange(0.5, 24.0)
        self._window_spin.setSingleStep(0.5)
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
        group = QGroupBox("Detail", self)
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
        self._window_spin.valueChanged.connect(self._on_window_changed)
        self._filter_spin.valueChanged.connect(self._on_filter_changed)
        self._detail_sample_combo.currentTextChanged.connect(self._on_sample_changed)
        self._trace_list.itemClicked.connect(self._on_trace_clicked)
        self._prev_button.clicked.connect(self.view_model.previous_detail_page)
        self._next_button.clicked.connect(self.view_model.next_detail_page)
        self._metric_combo.currentIndexChanged.connect(self._on_metric_changed)

    @Slot()
    def _refresh_state(self) -> None:
        self._sample_list.clear()
        for pair in self.view_model.sample_pairs:
            self._sample_list.addItem(pair.sample_name)

        self._normalize_checkbox.blockSignals(True)
        self._normalize_checkbox.setChecked(self.view_model.normalize_by_area)
        self._normalize_checkbox.setEnabled(self.view_model.normalization_available)
        self._normalize_checkbox.blockSignals(False)

        self._window_spin.blockSignals(True)
        self._window_spin.setValue(self.view_model.fit_window_hours)
        self._window_spin.blockSignals(False)

        self._filter_spin.blockSignals(True)
        self._filter_spin.setValue(self.view_model.area_filter_size)
        self._filter_spin.blockSignals(False)

        self._detail_sample_combo.blockSignals(True)
        self._detail_sample_combo.clear()
        self._detail_sample_combo.addItems(self.view_model.sample_names)
        if self.view_model.selected_sample in self.view_model.sample_names:
            self._detail_sample_combo.setCurrentText(self.view_model.selected_sample)
        self._detail_sample_combo.blockSignals(False)

        self._metric_combo.blockSignals(True)
        self._metric_combo.clear()
        for label, value in self.view_model.metric_options:
            self._metric_combo.addItem(label, value)
        if self.view_model.selected_metric is not None:
            index = self._metric_combo.findData(self.view_model.selected_metric)
            if index >= 0:
                self._metric_combo.setCurrentIndex(index)
        self._metric_combo.blockSignals(False)

        show_filter = (
            self.view_model.normalization_available
            and self.view_model.normalize_by_area
        )
        self._filter_label.setVisible(show_filter)
        self._filter_spin.setVisible(show_filter)
        self._filter_spin.setEnabled(show_filter and not self.view_model.running)

        self._run_button.setEnabled(not self.view_model.running)
        self._normalize_checkbox.setEnabled(
            not self.view_model.running and self.view_model.normalization_available
        )
        self._window_spin.setEnabled(not self.view_model.running)
        self._detail_sample_combo.setEnabled(bool(self.view_model.sample_names))
        self._prev_button.setEnabled(self.view_model.can_go_to_previous_detail_page)
        self._next_button.setEnabled(self.view_model.can_go_to_next_detail_page)
        self._page_label.setText(self.view_model.detail_page_label)
        self._stats_label.setText(self.view_model.detail_stats_text)

    @Slot()
    def _refresh_results(self) -> None:
        self._refresh_state()

        self._trace_list.blockSignals(True)
        self._trace_list.clear()
        for fov, cell in self.view_model.visible_trace_ids:
            item = QListWidgetItem(f"Cell {cell}")
            item.setData(Qt.ItemDataRole.UserRole, (fov, cell))
            color = self._row_color(fov, cell)
            if color is not None:
                item.setForeground(color)
            self._trace_list.addItem(item)
        self._trace_list.blockSignals(False)

        plot_data = self.view_model.selected_trace_plot_data
        if plot_data is None:
            self._trace_canvas.clear()
        else:
            self._trace_canvas.plot_lines(
                plot_data["lines_data"],
                plot_data["styles_data"],
                title=plot_data["title"],
                x_label="Time (hours)",
                y_label=plot_data["y_label"],
            )

        if not self.view_model.grouped_metric_values:
            self._boxplot_canvas.clear()
        else:
            self._boxplot_canvas.plot_boxplot(
                self.view_model.grouped_metric_values,
                title=(
                    f"Comparison of {self.view_model.selected_metric}"
                    if self.view_model.selected_metric
                    else ""
                ),
                x_label="Sample",
                y_label=self.view_model.selected_metric or "",
            )

        self._summary_table.setRowCount(len(self.view_model.summary_rows))
        for row_index, row_values in enumerate(self.view_model.summary_rows):
            for col_index, value in enumerate(row_values):
                text = f"{value:.3f}" if isinstance(value, float) else str(value)
                self._summary_table.setItem(
                    row_index, col_index, QTableWidgetItem(text)
                )

    def _row_color(self, fov: int, cell: int) -> QColor | None:
        row = self.view_model.result_row_for_cell(fov, cell)
        if row is None:
            return None
        success = bool(row.get("success", False))
        if not success:
            return QColor("red")
        if self.view_model.selected_metric != "onset_time":
            return QColor("green")
        r_squared = row.get("r_squared")
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
        self.view_model.set_fit_window_hours(float(self._window_spin.value()))
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
        self.view_model.set_fit_window_hours(float(value))

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
