"""BBox alignment tab view."""

import json
import math

from PySide6.QtCore import QSignalBlocker, Qt, Slot
from PySide6.QtGui import QCloseEvent, QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pyama_gui.apps.alignment import minimum_grid_spacing

from pyama_gui.app_view_model import AppViewModel
from pyama_gui.apps.bboxes.view_model import BBoxesViewModel
from pyama_gui.components import ViewCanvas
from pyama_gui.types import BBoxesViewState


class BBoxesView(QWidget):
    """Grid alignment and bbox export tab."""

    def __init__(
        self,
        app_view_model: AppViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.app_view_model = app_view_model
        self.view_model = BBoxesViewModel(app_view_model, self)
        self._canvas_ready = False
        self._selection_mode = False
        self._time_values: list[str] = []
        self._build_ui()
        self._connect_signals()
        self._refresh_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 920, 320])
        layout.addWidget(splitter, 1)

    def _build_left_panel(self) -> QWidget:
        panel = QGroupBox(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        layout.addWidget(self._create_section_header("Image"))
        image_form = QFormLayout()
        self._position_combo = QComboBox()
        self._channel_combo = QComboBox()
        self._time_slider = self._create_slider(0, 0)
        self._time_value_label = self._create_value_label("0")
        self._z_combo = QComboBox()
        image_form.addRow("Position", self._position_combo)
        image_form.addRow("Channel", self._channel_combo)
        image_form.addRow(
            "Time",
            self._create_slider_row(self._time_slider, self._time_value_label),
        )
        image_form.addRow("Z Slice", self._z_combo)
        layout.addLayout(image_form)

        layout.addSpacing(4)
        self._auto_contrast_button = QPushButton("Auto")
        layout.addWidget(
            self._create_section_header("Contrast", [self._auto_contrast_button])
        )
        contrast_layout = QVBoxLayout()
        contrast_layout.setContentsMargins(0, 0, 0, 0)
        contrast_layout.setSpacing(8)

        contrast_form = QFormLayout()
        self._contrast_min_slider = self._create_slider(0, 65534)
        self._contrast_min_label = self._create_value_label("0")
        self._contrast_max_slider = self._create_slider(1, 65535)
        self._contrast_max_label = self._create_value_label("65535")
        contrast_form.addRow(
            "Minimum",
            self._create_slider_row(
                self._contrast_min_slider, self._contrast_min_label
            ),
        )
        contrast_form.addRow(
            "Maximum",
            self._create_slider_row(
                self._contrast_max_slider, self._contrast_max_label
            ),
        )
        contrast_layout.addLayout(contrast_form)
        layout.addLayout(contrast_layout)
        layout.addStretch(1)
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(280)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self._canvas_view = ViewCanvas(self)
        layout.addWidget(self._canvas_view)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QGroupBox(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._reset_button = QPushButton("Reset")
        self._grid_enabled_button = QPushButton("Off")
        layout.addWidget(
            self._create_section_header(
                "Grid",
                [self._reset_button, self._grid_enabled_button],
            )
        )

        grid_form = QFormLayout()
        self._shape_combo = QComboBox()
        self._shape_combo.addItem("Square", "square")
        self._shape_combo.addItem("Hex", "hex")
        self._rotation_slider = self._create_slider(-1800, 1800)
        self._rotation_label = self._create_value_label("0.0°")
        self._spacing_a_input = self._create_number_input(1.0, 10000.0, 2)
        self._spacing_b_input = self._create_number_input(1.0, 10000.0, 2)
        self._cell_width_input = self._create_number_input(1.0, 10000.0, 2)
        self._cell_height_input = self._create_number_input(1.0, 10000.0, 2)
        self._tx_input = self._create_number_input(-100000.0, 100000.0, 2)
        self._ty_input = self._create_number_input(-100000.0, 100000.0, 2)
        self._opacity_slider = self._create_slider(0, 100)
        self._opacity_label = self._create_value_label("0.00")

        grid_form.addRow("Shape", self._shape_combo)
        grid_form.addRow(
            "Rotation",
            self._create_slider_row(self._rotation_slider, self._rotation_label),
        )
        grid_form.addRow(
            "Spacing",
            self._create_pair_input_row(
                "A",
                self._spacing_a_input,
                "B",
                self._spacing_b_input,
            ),
        )
        grid_form.addRow(
            "Cell",
            self._create_pair_input_row(
                "W",
                self._cell_width_input,
                "H",
                self._cell_height_input,
            ),
        )
        grid_form.addRow(
            "Offset",
            self._create_pair_input_row("X", self._tx_input, "Y", self._ty_input),
        )
        grid_form.addRow(
            "Opacity",
            self._create_slider_row(self._opacity_slider, self._opacity_label),
        )
        layout.addLayout(grid_form)

        layout.addSpacing(4)
        self._disable_edge_button = QPushButton("Disable Edge")
        self._save_button = QPushButton("Save")
        self._selection_mode_button = QPushButton("Off")
        layout.addWidget(
            self._create_section_header(
                "Select",
                [
                    self._disable_edge_button,
                    self._save_button,
                    self._selection_mode_button,
                ],
            )
        )

        self._included_label = self._create_value_label("0")
        self._included_label.setStyleSheet("font-weight: 600;")
        self._excluded_label = self._create_value_label("0")
        self._excluded_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(
            self._create_pair_value_row(
                "Included",
                self._included_label,
                "Excluded",
                self._excluded_label,
            )
        )

        self._save_path_label = QLabel("")
        self._save_path_label.setWordWrap(True)
        layout.addWidget(self._save_path_label)
        layout.addStretch(1)
        panel.setMinimumWidth(320)
        panel.setMaximumWidth(320)
        return panel

    @staticmethod
    def _create_slider(minimum: int, maximum: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setSingleStep(1)
        slider.setPageStep(max(1, (maximum - minimum) // 20))
        return slider

    @staticmethod
    def _create_number_input(
        minimum: float,
        maximum: float,
        decimals: int,
    ) -> QLineEdit:
        input_widget = QLineEdit()
        validator = QDoubleValidator(minimum, maximum, decimals, input_widget)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        input_widget.setValidator(validator)
        input_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        input_widget.setFixedWidth(72)
        return input_widget

    @staticmethod
    def _create_value_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setMinimumWidth(48)
        return label

    @staticmethod
    def _create_slider_row(slider: QWidget, tail: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(slider, 1)
        layout.addWidget(tail)
        return row

    @staticmethod
    def _create_pair_input_row(
        left_label: str,
        left_input: QWidget,
        right_label: str,
        right_input: QWidget,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel(left_label))
        layout.addWidget(left_input)
        layout.addSpacing(4)
        layout.addWidget(QLabel(right_label))
        layout.addWidget(right_input)
        layout.addStretch(1)
        return row

    @staticmethod
    def _create_pair_value_row(
        left_label: str,
        left_widget: QWidget,
        right_label: str,
        right_widget: QWidget,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(QLabel(left_label))
        layout.addWidget(left_widget)
        layout.addSpacing(8)
        layout.addWidget(QLabel(right_label))
        layout.addWidget(right_widget)
        layout.addStretch(1)
        return row

    @staticmethod
    def _create_section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: 600;")
        return label

    @staticmethod
    def _create_section_header(
        text: str,
        actions: list[QWidget] | None = None,
    ) -> QWidget:
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(BBoxesView._create_section_label(text))
        layout.addStretch(1)
        for action in actions or []:
            layout.addWidget(action)
        return header

    @staticmethod
    def _format_number(value: float, decimals: int) -> str:
        if decimals == 0:
            return str(int(round(value)))
        return f"{value:.{decimals}f}".rstrip("0").rstrip(".")

    @staticmethod
    def _set_number_input_value(widget: QLineEdit, value: float, decimals: int) -> None:
        blocker = QSignalBlocker(widget)
        widget.setText(BBoxesView._format_number(value, decimals))
        del blocker

    @staticmethod
    def _read_number_input_value(widget: QLineEdit, fallback: float) -> float:
        text = widget.text().strip()
        if not text:
            return fallback
        try:
            return float(text)
        except ValueError:
            return fallback

    def _connect_signals(self) -> None:
        self.view_model.state_changed.connect(self._refresh_state)
        self._position_combo.currentIndexChanged.connect(self._on_position_changed)
        self._channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        self._time_slider.valueChanged.connect(self._on_time_slider_changed)
        self._time_slider.sliderReleased.connect(self._commit_time_slider)
        self._z_combo.currentIndexChanged.connect(self._on_z_changed)
        self._auto_contrast_button.clicked.connect(
            self.view_model.auto_contrast_current_frame
        )
        self._contrast_min_slider.valueChanged.connect(self._on_contrast_slider_changed)
        self._contrast_max_slider.valueChanged.connect(self._on_contrast_slider_changed)
        self._contrast_min_slider.sliderReleased.connect(self._on_contrast_changed)
        self._contrast_max_slider.sliderReleased.connect(self._on_contrast_changed)
        self._reset_button.clicked.connect(self.view_model.reset_grid)
        self._grid_enabled_button.clicked.connect(self._on_grid_enabled_clicked)
        self._shape_combo.currentIndexChanged.connect(self._on_shape_changed)
        self._rotation_slider.valueChanged.connect(self._on_rotation_slider_changed)
        self._spacing_a_input.editingFinished.connect(self._on_grid_spacing_changed)
        self._spacing_b_input.editingFinished.connect(self._on_grid_spacing_changed)
        self._cell_width_input.editingFinished.connect(self._on_grid_cell_size_changed)
        self._cell_height_input.editingFinished.connect(self._on_grid_cell_size_changed)
        self._tx_input.editingFinished.connect(self._on_grid_offset_changed)
        self._ty_input.editingFinished.connect(self._on_grid_offset_changed)
        self._opacity_slider.valueChanged.connect(self._on_opacity_slider_changed)
        self._disable_edge_button.clicked.connect(self.view_model.disable_edge_cells)
        self._save_button.clicked.connect(self.view_model.save_current_bboxes)
        self._selection_mode_button.clicked.connect(self._on_selection_mode_clicked)
        self._canvas_view.message_received.connect(self._on_canvas_message)

    @Slot()
    def _refresh_state(self) -> None:
        state = self.view_model.state
        self._time_values = list(state.time_values)

        self._included_label.setText(str(state.included_count))
        self._excluded_label.setText(str(state.excluded_count))
        self._save_path_label.setText(
            f"Save Path: {state.save_path_label}" if state.save_path_label else ""
        )

        self._set_combo_items(
            self._position_combo,
            state.position_options,
            state.selected_position,
        )
        self._set_combo_items(
            self._channel_combo,
            state.channel_options,
            state.selected_channel,
        )
        self._set_combo_items(self._z_combo, state.z_options, state.selected_z)
        self._set_time_controls(state)
        self._set_contrast_controls(state)
        self._set_grid_controls(state)
        self._set_control_states(state)
        self._publish_canvas_state()

    def _set_combo_items(
        self,
        combo: QComboBox,
        options: list[tuple[str, int]],
        current: int | None,
    ) -> None:
        blocker = QSignalBlocker(combo)
        combo.clear()
        for label, value in options:
            combo.addItem(label, value)
        if current is not None:
            index = combo.findData(current)
            if index >= 0:
                combo.setCurrentIndex(index)
        del blocker

    def _set_time_controls(self, state: BBoxesViewState) -> None:
        blocker = QSignalBlocker(self._time_slider)
        self._time_slider.setRange(0, state.frame_max)
        self._time_slider.setValue(state.selected_frame)
        self._time_value_label.setText(state.time_value_label)
        del blocker

    def _set_contrast_controls(self, state: BBoxesViewState) -> None:
        min_upper = max(state.contrast_domain_min, state.contrast_max - 1)
        max_lower = min(state.contrast_domain_max, state.contrast_min + 1)
        blockers = [
            QSignalBlocker(self._contrast_min_slider),
            QSignalBlocker(self._contrast_max_slider),
        ]
        self._contrast_min_slider.setRange(state.contrast_domain_min, min_upper)
        self._contrast_max_slider.setRange(max_lower, state.contrast_domain_max)
        self._contrast_min_slider.setValue(state.contrast_min)
        self._contrast_max_slider.setValue(state.contrast_max)
        self._contrast_min_label.setText(str(state.contrast_min))
        self._contrast_max_label.setText(str(state.contrast_max))
        del blockers

    def _set_contrast_preview(self, minimum: int, maximum: int) -> None:
        blockers = [
            QSignalBlocker(self._contrast_min_slider),
            QSignalBlocker(self._contrast_max_slider),
        ]
        self._contrast_min_slider.setValue(minimum)
        self._contrast_max_slider.setValue(maximum)
        self._contrast_min_label.setText(str(minimum))
        self._contrast_max_label.setText(str(maximum))
        del blockers

    def _set_grid_controls(self, state: BBoxesViewState) -> None:
        grid = state.grid_values
        blockers = [
            QSignalBlocker(self._shape_combo),
            QSignalBlocker(self._rotation_slider),
            QSignalBlocker(self._opacity_slider),
        ]
        self._grid_enabled_button.setText(
            "On" if bool(grid.get("enabled", False)) else "Off"
        )
        shape = str(grid.get("shape", "square"))
        shape_index = self._shape_combo.findData(shape)
        if shape_index >= 0:
            self._shape_combo.setCurrentIndex(shape_index)
        rotation_degrees = math.degrees(float(grid.get("rotation", 0.0)))
        self._rotation_slider.setValue(int(round(rotation_degrees * 10)))
        self._rotation_label.setText(f"{rotation_degrees:.1f}°")
        self._set_number_input_value(
            self._spacing_a_input,
            float(grid.get("spacingA", 1.0)),
            2,
        )
        self._set_number_input_value(
            self._spacing_b_input,
            float(grid.get("spacingB", 1.0)),
            2,
        )
        self._set_number_input_value(
            self._cell_width_input,
            float(grid.get("cellWidth", 1.0)),
            2,
        )
        self._set_number_input_value(
            self._cell_height_input,
            float(grid.get("cellHeight", 1.0)),
            2,
        )
        self._set_number_input_value(self._tx_input, float(grid.get("tx", 0.0)), 2)
        self._set_number_input_value(self._ty_input, float(grid.get("ty", 0.0)), 2)
        opacity = float(grid.get("opacity", 0.35))
        self._opacity_slider.setValue(int(round(opacity * 100)))
        self._opacity_label.setText(f"{opacity:.2f}")
        del blockers

        min_spacing = minimum_grid_spacing(
            float(grid.get("cellWidth", 1.0)),
            float(grid.get("cellHeight", 1.0)),
        )
        self._set_validator_bottom(self._spacing_a_input, min_spacing)
        self._set_validator_bottom(self._spacing_b_input, min_spacing)
        self._set_validator_bottom(self._cell_width_input, 1.0)
        self._set_validator_bottom(self._cell_height_input, 1.0)
        self._set_validator_bottom(self._tx_input, -100000.0)
        self._set_validator_bottom(self._ty_input, -100000.0)

    @staticmethod
    def _set_validator_bottom(widget: QLineEdit, minimum: float) -> None:
        validator = widget.validator()
        if isinstance(validator, QDoubleValidator):
            validator.setBottom(minimum)

    def _set_control_states(self, state: BBoxesViewState) -> None:
        has_selection = (
            state.selected_position is not None
            and state.selected_channel is not None
            and state.selected_z is not None
        )
        has_frame = state.current_image is not None
        grid_enabled = bool(state.grid_values.get("enabled", False))
        selection_enabled = has_frame and grid_enabled

        self._position_combo.setEnabled(bool(state.position_options))
        self._channel_combo.setEnabled(bool(state.channel_options))
        self._time_slider.setEnabled(has_selection and state.frame_max > 0)
        self._z_combo.setEnabled(bool(state.z_options))
        self._auto_contrast_button.setEnabled(has_frame)
        self._contrast_min_slider.setEnabled(has_frame)
        self._contrast_max_slider.setEnabled(has_frame)
        self._reset_button.setEnabled(has_selection)
        self._grid_enabled_button.setEnabled(has_selection)
        self._shape_combo.setEnabled(has_selection)
        self._rotation_slider.setEnabled(has_selection)
        self._spacing_a_input.setEnabled(has_selection)
        self._spacing_b_input.setEnabled(has_selection)
        self._cell_width_input.setEnabled(has_selection)
        self._cell_height_input.setEnabled(has_selection)
        self._tx_input.setEnabled(has_selection)
        self._ty_input.setEnabled(has_selection)
        self._opacity_slider.setEnabled(has_selection)
        self._disable_edge_button.setEnabled(state.can_disable_edge)
        self._save_button.setEnabled(state.can_save and not state.loading_frame)
        self._selection_mode_button.setEnabled(selection_enabled)
        if not selection_enabled and self._selection_mode:
            self._selection_mode = False
        self._selection_mode_button.setText("On" if self._selection_mode else "Off")
        if not selection_enabled:
            self._publish_canvas_state()

    @Slot(int)
    def _on_position_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self._position_combo.itemData(index)
        if value is not None:
            self.view_model.set_selected_position(int(value))

    @Slot(int)
    def _on_channel_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self._channel_combo.itemData(index)
        if value is not None:
            self.view_model.set_selected_channel(int(value))

    @Slot(int)
    def _on_time_slider_changed(self, value: int) -> None:
        if not self._time_values:
            self._time_value_label.setText("0")
            return
        index = max(0, min(int(value), len(self._time_values) - 1))
        self._time_value_label.setText(self._time_values[index])
        if not self._time_slider.isSliderDown():
            self._commit_time_slider()

    def _commit_time_slider(self) -> None:
        index = int(self._time_slider.value())
        self.view_model.set_selected_frame(index)

    @Slot(int)
    def _on_z_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self._z_combo.itemData(index)
        if value is not None:
            self.view_model.set_selected_z(int(value))

    @Slot()
    def _on_contrast_slider_changed(self) -> None:
        preferred = "min" if self.sender() is self._contrast_min_slider else "max"
        minimum, maximum = self._normalize_contrast_values(
            self._contrast_min_slider.value(),
            self._contrast_max_slider.value(),
            preferred,
        )
        self._set_contrast_preview(minimum, maximum)
        if not (
            self._contrast_min_slider.isSliderDown()
            or self._contrast_max_slider.isSliderDown()
        ):
            self._on_contrast_changed()

    @Slot()
    def _on_contrast_changed(self) -> None:
        preferred = "min" if self.sender() is self._contrast_min_slider else "max"
        minimum, maximum = self._normalize_contrast_values(
            self._contrast_min_slider.value(),
            self._contrast_max_slider.value(),
            preferred,
        )
        self.view_model.commit_contrast_window(minimum, maximum)

    def _normalize_contrast_values(
        self,
        minimum: int,
        maximum: int,
        preferred: str,
    ) -> tuple[int, int]:
        domain_min = int(self._contrast_min_slider.minimum())
        domain_max = int(self._contrast_max_slider.maximum())
        next_min = max(domain_min, min(int(minimum), max(domain_min, domain_max - 1)))
        next_max = max(min(domain_max, int(maximum)), min(domain_max, domain_min + 1))
        if next_min >= next_max:
            if preferred == "min":
                next_min = max(domain_min, next_max - 1)
            else:
                next_max = min(domain_max, next_min + 1)
        return next_min, next_max

    @Slot()
    def _on_grid_enabled_clicked(self) -> None:
        is_enabled = self._grid_enabled_button.text() == "On"
        self.view_model.set_grid_patch({"enabled": not is_enabled})

    @Slot(int)
    def _on_shape_changed(self, index: int) -> None:
        if index < 0:
            return
        value = self._shape_combo.itemData(index)
        if value is not None:
            self.view_model.set_grid_patch({"shape": str(value)})

    @Slot(int)
    def _on_rotation_slider_changed(self, value: int) -> None:
        degrees = value / 10.0
        self._rotation_label.setText(f"{degrees:.1f}°")
        self.view_model.set_grid_patch({"rotation": math.radians(degrees)})

    @Slot()
    def _on_grid_spacing_changed(self) -> None:
        current = self.view_model.state.grid_values
        min_spacing = minimum_grid_spacing(
            float(current.get("cellWidth", 1.0)),
            float(current.get("cellHeight", 1.0)),
        )
        spacing_a = max(
            min_spacing,
            self._read_number_input_value(
                self._spacing_a_input,
                float(current.get("spacingA", 1.0)),
            ),
        )
        spacing_b = max(
            min_spacing,
            self._read_number_input_value(
                self._spacing_b_input,
                float(current.get("spacingB", 1.0)),
            ),
        )
        self.view_model.set_grid_patch({"spacingA": spacing_a, "spacingB": spacing_b})

    @Slot()
    def _on_grid_cell_size_changed(self) -> None:
        current = self.view_model.state.grid_values
        cell_width = max(
            1.0,
            self._read_number_input_value(
                self._cell_width_input,
                float(current.get("cellWidth", 1.0)),
            ),
        )
        cell_height = max(
            1.0,
            self._read_number_input_value(
                self._cell_height_input,
                float(current.get("cellHeight", 1.0)),
            ),
        )
        self.view_model.set_grid_patch(
            {"cellWidth": cell_width, "cellHeight": cell_height}
        )

    @Slot()
    def _on_grid_offset_changed(self) -> None:
        current = self.view_model.state.grid_values
        tx = self._read_number_input_value(
            self._tx_input, float(current.get("tx", 0.0))
        )
        ty = self._read_number_input_value(
            self._ty_input, float(current.get("ty", 0.0))
        )
        self.view_model.set_grid_patch({"tx": tx, "ty": ty})

    @Slot(int)
    def _on_opacity_slider_changed(self, value: int) -> None:
        opacity = value / 100.0
        self._opacity_label.setText(f"{opacity:.2f}")
        self.view_model.set_grid_patch({"opacity": opacity})

    @Slot()
    def _on_selection_mode_clicked(self) -> None:
        enabled = bool(
            (self._selection_mode_button.text() == "Off")
            and self._selection_mode_button.isEnabled()
        )
        self._selection_mode = enabled
        self._selection_mode_button.setText("On" if enabled else "Off")
        self._publish_canvas_state()

    def _publish_canvas_state(self) -> None:
        if not self._canvas_ready:
            return
        self._canvas_view.publish_state(
            self.view_model.canvas_payload(selection_mode=self._selection_mode)
        )

    @Slot(str)
    def _on_canvas_message(self, message: str) -> None:
        try:
            envelope = json.loads(message)
        except json.JSONDecodeError:
            return

        if not isinstance(envelope, dict):
            return
        message_type = envelope.get("type")
        payload = envelope.get("payload")
        if message_type == "ready":
            self._canvas_ready = True
            self._publish_canvas_state()
            return
        if message_type == "gridChanged":
            self.view_model.handle_canvas_grid_changed(payload)
            return
        if message_type == "excludedCellsToggled":
            self.view_model.handle_canvas_excluded_cells_toggled(payload)
            return
        if message_type == "frameLoaded":
            self.view_model.handle_canvas_frame_loaded(payload)
            return
        if message_type == "frameLoadFailed":
            self.view_model.handle_canvas_frame_load_failed(payload)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.view_model.shutdown()
        super().closeEvent(event)
