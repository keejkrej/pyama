"""Consolidated view for the visualization tab."""

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.components import PyQtGraphImageView
from pyama_gui.types.visualization import VisualizationViewState
from pyama_gui.apps.visualization.view_model import VisualizationViewModel
from pyama_gui.widgets import MplCanvas


class VisualizationView(QWidget):
    """Consolidated visualization tab view."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = VisualizationViewModel(app_view_model, self)
        self._build_ui()
        self._connect_signals()
        self._refresh_state()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.addWidget(self._build_workspace_section(), 1)
        layout.addWidget(self._build_image_section(), 2)
        layout.addWidget(self._build_trace_section(), 1)

    def _build_workspace_section(self) -> QGroupBox:
        group = QGroupBox("Workspace")
        layout = QVBoxLayout(group)

        self._project_details_text = QTextEdit()
        self._project_details_text.setReadOnly(True)
        layout.addWidget(self._project_details_text)

        position_row = QHBoxLayout()
        self._position_spinbox = QSpinBox()
        self._position_max_label = QLabel("/ 0")
        position_row.addWidget(QLabel("Position:"))
        position_row.addStretch()
        position_row.addWidget(self._position_spinbox)
        position_row.addWidget(self._position_max_label)
        layout.addLayout(position_row)

        self._channels_list = QListWidget()
        self._channels_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self._channels_list.setEditTriggers(QListWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._channels_list)

        self._visualize_button = QPushButton("Start Visualization")
        layout.addWidget(self._visualize_button)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)
        return group

    def _build_image_section(self) -> QGroupBox:
        group = QGroupBox("Image Viewer")
        layout = QVBoxLayout(group)

        controls_layout = QVBoxLayout()
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Data Type:"))
        self._data_type_combo = QComboBox()
        first_row.addWidget(self._data_type_combo)
        controls_layout.addLayout(first_row)

        second_row = QHBoxLayout()
        self._prev_frame_10_button = QPushButton("<<")
        self._prev_frame_button = QPushButton("<")
        self._frame_label = QLabel("Frame 0/0")
        self._frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_frame_button = QPushButton(">")
        self._next_frame_10_button = QPushButton(">>")
        second_row.addWidget(self._prev_frame_10_button)
        second_row.addWidget(self._prev_frame_button)
        second_row.addWidget(self._frame_label)
        second_row.addWidget(self._next_frame_button)
        second_row.addWidget(self._next_frame_10_button)
        controls_layout.addLayout(second_row)
        layout.addLayout(controls_layout)

        self._image_viewer = PyQtGraphImageView(self)
        layout.addWidget(self._image_viewer)
        return group

    def _build_trace_section(self) -> QGroupBox:
        group = QGroupBox("Trace Plot")
        outer_layout = QVBoxLayout(group)

        selection_row = QHBoxLayout()
        selection_row.addWidget(QLabel("Feature:"))
        self._feature_dropdown = QComboBox()
        selection_row.addWidget(self._feature_dropdown)
        outer_layout.addLayout(selection_row)

        self._trace_canvas = MplCanvas(self)
        outer_layout.addWidget(self._trace_canvas)

        self._trace_list = QListWidget()
        self._trace_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._trace_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        outer_layout.addWidget(self._trace_list)

        pagination_row = QHBoxLayout()
        self._trace_page_label = QLabel("Page 1 of 1")
        self._trace_prev_button = QPushButton("Previous")
        self._trace_next_button = QPushButton("Next")
        pagination_row.addWidget(self._trace_page_label)
        pagination_row.addWidget(self._trace_prev_button)
        pagination_row.addWidget(self._trace_next_button)
        outer_layout.addLayout(pagination_row)

        self._save_button = QPushButton("Save Inspected CSV")
        outer_layout.addWidget(self._save_button)
        return group

    def _connect_signals(self) -> None:
        self.view_model.state_changed.connect(self._refresh_state)
        self._visualize_button.clicked.connect(self.view_model.start_visualization)
        self._data_type_combo.currentTextChanged.connect(
            self.view_model.set_selected_data_type
        )
        self._prev_frame_button.clicked.connect(lambda: self.view_model.step_frame(-1))
        self._next_frame_button.clicked.connect(lambda: self.view_model.step_frame(1))
        self._prev_frame_10_button.clicked.connect(
            lambda: self.view_model.step_frame(-10)
        )
        self._next_frame_10_button.clicked.connect(
            lambda: self.view_model.step_frame(10)
        )
        self._image_viewer.overlay_clicked.connect(self._on_overlay_clicked)
        self._image_viewer.overlay_right_clicked.connect(self._on_overlay_right_clicked)
        self._feature_dropdown.currentTextChanged.connect(
            self.view_model.set_selected_feature
        )
        self._trace_list.itemClicked.connect(self._on_trace_item_clicked)
        self._trace_list.customContextMenuRequested.connect(
            self._on_trace_list_right_clicked
        )
        self._trace_prev_button.clicked.connect(self.view_model.previous_trace_page)
        self._trace_next_button.clicked.connect(self.view_model.next_trace_page)
        self._save_button.clicked.connect(self.view_model.save_inspected_csv)
        self._channels_list.itemSelectionChanged.connect(
            self._on_channel_selection_changed
        )
        self._position_spinbox.valueChanged.connect(
            self.view_model.set_selected_position
        )

    @Slot()
    def _refresh_state(self) -> None:
        state = self.view_model.state
        self._project_details_text.setPlainText(state.details_text)

        self._channels_list.blockSignals(True)
        self._channels_list.clear()
        for channel in state.available_channels:
            item = QListWidgetItem(channel)
            item.setData(Qt.ItemDataRole.UserRole, channel)
            if channel in state.selected_channels:
                item.setSelected(True)
            self._channels_list.addItem(item)
        self._channels_list.blockSignals(False)

        self._visualize_button.setEnabled(
            not state.loading_visualization and state.can_visualize
        )
        self._visualize_button.setText(
            "Loading..." if state.loading_visualization else "Start Visualization"
        )

        self._progress_bar.setVisible(state.loading_visualization)
        if state.loading_visualization:
            self._progress_bar.setRange(0, 0)

        self._position_spinbox.blockSignals(True)
        self._position_spinbox.setRange(state.min_position, state.max_position)
        self._position_spinbox.setValue(state.selected_position)
        self._position_spinbox.blockSignals(False)
        self._position_max_label.setText(f"/ {state.max_position}")

        self._data_type_combo.blockSignals(True)
        self._data_type_combo.clear()
        self._data_type_combo.addItems(state.data_types)
        if state.selected_data_type:
            index = self._data_type_combo.findText(state.selected_data_type)
            if index >= 0:
                self._data_type_combo.setCurrentIndex(index)
        self._data_type_combo.blockSignals(False)

        self._feature_dropdown.blockSignals(True)
        self._feature_dropdown.clear()
        self._feature_dropdown.addItems(state.trace_feature_options)
        if state.selected_feature:
            index = self._feature_dropdown.findText(state.selected_feature)
            if index >= 0:
                self._feature_dropdown.setCurrentIndex(index)
        self._feature_dropdown.blockSignals(False)

        self._frame_label.setText(state.frame_label)
        self._render_image_state(state)
        self._render_trace_plot(state)
        self._render_trace_rows(state)
        self._trace_page_label.setText(state.trace_page.label)
        self._trace_prev_button.setEnabled(state.trace_page.can_previous)
        self._trace_next_button.setEnabled(state.trace_page.can_next)
        self._save_button.setEnabled(state.can_save)

    def _render_image_state(self, state: VisualizationViewState) -> None:
        if state.current_image is None:
            self._image_viewer.clear()
            return
        self._image_viewer.set_image(state.current_image)
        self._image_viewer.set_overlays(state.overlays)

    def _render_trace_plot(self, state: VisualizationViewState) -> None:
        if state.trace_plot is None:
            self._trace_canvas.clear()
            return
        self._trace_canvas.plot_lines(
            state.trace_plot.lines_data,
            state.trace_plot.styles_data,
            title=state.trace_plot.title,
            x_label=state.trace_plot.x_label,
            y_label=state.trace_plot.y_label,
        )

    def _render_trace_rows(self, state: VisualizationViewState) -> None:
        self._trace_list.blockSignals(True)
        self._trace_list.clear()
        for row in state.trace_rows:
            item = QListWidgetItem(row.label)
            item.setData(Qt.ItemDataRole.UserRole, row.value)
            if row.color is not None:
                item.setForeground(QColor(row.color))
            self._trace_list.addItem(item)
        self._trace_list.blockSignals(False)

    @Slot()
    def _on_channel_selection_changed(self) -> None:
        selected_channels = [
            str(item.data(Qt.ItemDataRole.UserRole))
            for item in self._channels_list.selectedItems()
        ]
        self.view_model.set_selected_channels(selected_channels)

    @Slot(str)
    def _on_overlay_clicked(self, overlay_id: str) -> None:
        if overlay_id.startswith("trace_"):
            self.view_model.select_trace(overlay_id.split("_", 1)[1])

    @Slot(str)
    def _on_overlay_right_clicked(self, overlay_id: str) -> None:
        if overlay_id.startswith("trace_"):
            self.view_model.toggle_trace_quality(overlay_id.split("_", 1)[1])

    @Slot(QListWidgetItem)
    def _on_trace_item_clicked(self, item: QListWidgetItem) -> None:
        trace_id = item.data(Qt.ItemDataRole.UserRole)
        if trace_id:
            self.view_model.select_trace(str(trace_id))

    @Slot(object)
    def _on_trace_list_right_clicked(self, pos) -> None:
        item = self._trace_list.itemAt(pos)
        if item is None:
            return
        trace_id = item.data(Qt.ItemDataRole.UserRole)
        if trace_id:
            self.view_model.toggle_trace_quality(str(trace_id))
