"""Input panel for the processing workflow."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_pro.constants import DEFAULT_DIR

logger = logging.getLogger(__name__)


class InputPanel(QWidget):
    """Collect microscopy and channel selections for processing."""

    microscopy_selected = Signal(object)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._phase_channel: int | None = None
        self._fl_features: dict[int, list[str]] = {}
        self._pc_features: list[str] = []
        self._available_fl_features: list[str] = []
        self._available_pc_features: list[str] = []
        self._build_ui()
        self._connect_signals()
        self.reset()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Input")
        group_layout = QVBoxLayout(group)

        header = QHBoxLayout()
        header.addWidget(QLabel("Microscopy File:"))
        header.addStretch()
        self._microscopy_button = QPushButton("Browse")
        header.addWidget(self._microscopy_button)
        group_layout.addLayout(header)

        self._microscopy_path_field = QLineEdit()
        self._microscopy_path_field.setReadOnly(True)
        group_layout.addWidget(self._microscopy_path_field)

        group_layout.addWidget(self._build_channel_section())

        layout.addWidget(group)

    def _build_channel_section(self) -> QGroupBox:
        group = QGroupBox("Channels")
        layout = QVBoxLayout(group)

        pc_layout = QVBoxLayout()
        pc_layout.addWidget(QLabel("Phase Contrast"))
        self._pc_combo = QComboBox()
        pc_layout.addWidget(self._pc_combo)
        layout.addLayout(pc_layout)

        pc_feature_layout = QVBoxLayout()
        pc_feature_layout.addWidget(QLabel("Phase Contrast Features"))
        self._pc_feature_list = QListWidget()
        self._pc_feature_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        pc_feature_layout.addWidget(self._pc_feature_list)
        layout.addLayout(pc_feature_layout)

        fl_layout = QVBoxLayout()
        fl_layout.addWidget(QLabel("Fluorescence"))

        add_layout = QHBoxLayout()
        self._fl_channel_combo = QComboBox()
        add_layout.addWidget(self._fl_channel_combo)
        self._feature_combo = QComboBox()
        add_layout.addWidget(self._feature_combo)
        self._add_button = QPushButton("Add")
        add_layout.addWidget(self._add_button)
        fl_layout.addLayout(add_layout)

        mapping_layout = QVBoxLayout()
        mapping_layout.addWidget(QLabel("Fluorescence Features"))
        self._mapping_list = QListWidget()
        self._mapping_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        mapping_layout.addWidget(self._mapping_list)
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.setEnabled(False)
        mapping_layout.addWidget(self._remove_button)
        fl_layout.addLayout(mapping_layout)

        layout.addLayout(fl_layout)
        return group

    def _connect_signals(self) -> None:
        self._microscopy_button.clicked.connect(self._on_microscopy_clicked)
        self._pc_combo.currentIndexChanged.connect(self._on_pc_channel_selection)
        self._add_button.clicked.connect(self._on_add_channel_feature)
        self._remove_button.clicked.connect(self._on_remove_selected)
        self._mapping_list.itemSelectionChanged.connect(
            self._on_mapping_selection_changed
        )
        self._pc_feature_list.itemSelectionChanged.connect(self._on_pc_features_changed)

    @property
    def phase_channel(self) -> int | None:
        return self._phase_channel

    @property
    def fl_features(self) -> dict[int, list[str]]:
        return {
            channel: list(features) for channel, features in self._fl_features.items()
        }

    @property
    def pc_features(self) -> list[str]:
        return list(self._pc_features)

    def reset(self) -> None:
        self._phase_channel = None
        self._fl_features = {}
        self._pc_features = []
        self._available_fl_features = []
        self._available_pc_features = []

        self.display_microscopy_path(None)

        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        self._pc_combo.blockSignals(False)

        self._fl_channel_combo.blockSignals(True)
        self._fl_channel_combo.clear()
        self._fl_channel_combo.blockSignals(False)

        self._feature_combo.blockSignals(True)
        self._feature_combo.clear()
        self._feature_combo.blockSignals(False)

        self._pc_feature_list.blockSignals(True)
        self._pc_feature_list.clear()
        self._pc_feature_list.blockSignals(False)

        self._mapping_list.clear()
        self._mapping_list.clearSelection()
        self._remove_button.setEnabled(False)

    @Slot()
    def _on_microscopy_clicked(self) -> None:
        logger.debug(
            "UI Click: Microscopy file browse button (start_dir=%s)", DEFAULT_DIR
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            DEFAULT_DIR,
            "Microscopy Files (*.nd2 *.czi);;ND2 Files (*.nd2);;CZI Files (*.czi);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return

        path_obj = Path(file_path)
        try:
            size_mb = path_obj.stat().st_size / (1024 * 1024)
            size_text = f"{size_mb:.1f} MB"
        except OSError:
            size_text = "unknown size"

        logger.info(
            "Microscopy file chosen: %s (size=%s, suffix=%s)",
            file_path,
            size_text,
            path_obj.suffix.lower(),
        )
        self.microscopy_selected.emit(path_obj)

    def display_microscopy_path(self, path: Path | None) -> None:
        if path:
            self._microscopy_path_field.setText(path.name)
        else:
            self._microscopy_path_field.setText("No microscopy file selected")

    def load_microscopy_metadata(self, metadata: MicroscopyMetadata) -> None:
        logger.debug("UI Action: Loading microscopy metadata into input panel")
        phase_channels: list[tuple[str, int | None]] = []
        fluorescence_channels: list[tuple[str, int]] = []

        for i, channel_name in enumerate(metadata.channel_names):
            label = f"{i}: {channel_name}" if channel_name else str(i)
            phase_channels.append((label, i))
            fluorescence_channels.append((label, i))

        self.set_channel_options(phase_channels, fluorescence_channels)

    def set_channel_options(
        self,
        phase_channels: list[tuple[str, int | None]],
        fluorescence_channels: list[tuple[str, int]],
    ) -> None:
        self._available_fl_features = list_fluorescence_features()
        self._available_pc_features = list_phase_features()

        self._pc_combo.blockSignals(True)
        self._pc_combo.clear()
        for label, value in phase_channels:
            self._pc_combo.addItem(label, value)
        self._pc_combo.blockSignals(False)
        if self._pc_combo.count():
            self._pc_combo.setCurrentIndex(0)
            self._on_pc_channel_selection()

        self._fl_channel_combo.blockSignals(True)
        self._fl_channel_combo.clear()
        for label, value in fluorescence_channels:
            self._fl_channel_combo.addItem(label, value)
        self._fl_channel_combo.blockSignals(False)
        if self._fl_channel_combo.count():
            self._fl_channel_combo.setCurrentIndex(0)

        self._feature_combo.blockSignals(True)
        self._feature_combo.clear()
        for feature in self._available_fl_features:
            self._feature_combo.addItem(feature)
        self._feature_combo.blockSignals(False)
        if self._feature_combo.count():
            self._feature_combo.setCurrentIndex(0)

        self._pc_feature_list.blockSignals(True)
        self._pc_feature_list.clear()
        for feature in self._available_pc_features:
            item = QListWidgetItem(feature)
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._pc_feature_list.addItem(item)
        self._pc_feature_list.blockSignals(False)

        self._pc_features = []
        self._sync_pc_feature_selections()
        self._fl_features = {}
        self._update_mapping_display()
        self._mapping_list.clearSelection()
        self._remove_button.setEnabled(False)

    def apply_selected_channels(
        self,
        *,
        phase: int | None,
        fl_features: dict[int, list[str]] | None,
        pc_features: list[str] | None = None,
    ) -> None:
        self._pc_combo.blockSignals(True)
        try:
            if phase is None:
                self._pc_combo.setCurrentIndex(0)
            else:
                index = self._pc_combo.findData(phase)
                if index != -1:
                    self._pc_combo.setCurrentIndex(index)
        finally:
            self._pc_combo.blockSignals(False)

        normalized: dict[int, list[str]] = {}
        if fl_features:
            for channel, features in fl_features.items():
                if not isinstance(channel, int) or not features:
                    continue
                normalized[channel] = sorted({str(feature) for feature in features})

        self._fl_features = normalized
        self._update_mapping_display()
        self._mapping_list.clearSelection()
        self._remove_button.setEnabled(False)

        self._pc_features = sorted(pc_features or [])
        self._sync_pc_feature_selections()

    @Slot()
    def _on_add_channel_feature(self) -> None:
        channel_data = self._fl_channel_combo.currentData()
        feature = self._feature_combo.currentText()
        if channel_data is None or not feature:
            return

        channel_idx = int(channel_data)
        if channel_idx not in self._fl_features:
            self._fl_features[channel_idx] = []
        if feature not in self._fl_features[channel_idx]:
            self._fl_features[channel_idx].append(feature)
            self._fl_features[channel_idx].sort()

        self._update_mapping_display()
        logger.debug(
            "Added mapping: Channel %d -> %s (total_features_for_channel=%d, total_channels=%d)",
            channel_idx,
            feature,
            len(self._fl_features[channel_idx]),
            len(self._fl_features),
        )

    def _update_mapping_display(self) -> None:
        self._mapping_list.clear()
        for channel_idx in sorted(self._fl_features.keys()):
            features = self._fl_features[channel_idx]
            combo_index = self._fl_channel_combo.findData(channel_idx)
            channel_label = (
                self._fl_channel_combo.itemText(combo_index)
                if combo_index != -1
                else str(channel_idx)
            )
            if not channel_label:
                channel_label = str(channel_idx)
            for feature in features:
                item = QListWidgetItem(f"{channel_label} -> {feature}")
                item.setData(Qt.ItemDataRole.UserRole, (channel_idx, feature))
                self._mapping_list.addItem(item)

    @Slot()
    def _on_mapping_selection_changed(self) -> None:
        self._remove_button.setEnabled(bool(self._mapping_list.selectedItems()))

    @Slot()
    def _on_remove_selected(self) -> None:
        for item in self._mapping_list.selectedItems():
            self._remove_mapping(item)

    @Slot()
    def _on_pc_features_changed(self) -> None:
        selected_items = self._pc_feature_list.selectedItems()
        self._pc_features = sorted(item.text() for item in selected_items)
        logger.debug(
            "Phase features updated - selected=%s (count=%d)",
            self._pc_features,
            len(self._pc_features),
        )

    def _remove_mapping(self, item: QListWidgetItem) -> None:
        channel_idx, feature = item.data(Qt.ItemDataRole.UserRole)
        if channel_idx in self._fl_features and feature in self._fl_features[channel_idx]:
            self._fl_features[channel_idx].remove(feature)
            if not self._fl_features[channel_idx]:
                del self._fl_features[channel_idx]
            self._update_mapping_display()
            logger.debug(
                "Removed mapping: Channel %d -> %s (remaining_features_for_channel=%d)",
                channel_idx,
                feature,
                len(self._fl_features.get(channel_idx, [])),
            )

    def _sync_pc_feature_selections(self) -> None:
        self._pc_feature_list.blockSignals(True)
        try:
            self._pc_feature_list.clearSelection()
            if self._pc_features:
                selected = set(self._pc_features)
                for idx in range(self._pc_feature_list.count()):
                    item = self._pc_feature_list.item(idx)
                    item.setSelected(item.text() in selected)
        finally:
            self._pc_feature_list.blockSignals(False)

    @Slot()
    def _on_pc_channel_selection(self) -> None:
        if self._pc_combo.count() == 0:
            return
        phase_data = self._pc_combo.currentData()
        self._phase_channel = int(phase_data) if isinstance(phase_data, int) else None
        logger.debug(
            "Channels updated - phase=%s, pc_features=%s, fl_features=%s",
            self._phase_channel,
            self._pc_features,
            self._fl_features,
        )
