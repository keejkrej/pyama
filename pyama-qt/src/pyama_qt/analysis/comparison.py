"""Comparison panel for loading and comparing multiple sample CSV files.

This module provides the ComparisonPanel widget which contains the controls
and samples functionality that was previously in AnalysisTab.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pyama_core.io.analysis_csv import load_analysis_csv
from pyama_qt.constants import DEFAULT_DIR
from pyama_qt.utils import WorkerHandle, start_worker

logger = logging.getLogger(__name__)

THUMBNAIL_WIDTH = 200
THUMBNAIL_HEIGHT = 150
GRID_COLUMNS = 4


class SampleCard(QFrame):
    """A clickable card displaying a sample thumbnail and info."""

    double_clicked = Signal(Path)  # Emitted on double-click with sample path

    def __init__(
        self,
        csv_path: Path,
        cell_count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._csv_path = csv_path
        self._cell_count = cell_count

        self._build_ui()
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Thumbnail placeholder
        self._thumbnail_label = QLabel()
        self._thumbnail_label.setFixedSize(THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT)
        self._thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumbnail_label.setStyleSheet("background-color: #f0f0f0;")
        self._thumbnail_label.setText("Loading...")
        layout.addWidget(self._thumbnail_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Filename label
        filename_label = QLabel(self._csv_path.name)
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(filename_label)

        # Cell count label
        count_label = QLabel(f"{self._cell_count} cells")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet("color: #666;")
        layout.addWidget(count_label)

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        """Set the thumbnail image."""
        scaled = pixmap.scaled(
            THUMBNAIL_WIDTH,
            THUMBNAIL_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumbnail_label.setPixmap(scaled)

    def mouseDoubleClickEvent(self, event) -> None:
        """Handle double-click event."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._csv_path)
        super().mouseDoubleClickEvent(event)


class ThumbnailWorker(QObject):
    """Background worker for generating sample thumbnails with consistent axes.

    This worker generates thumbnails for all samples using the same x and y 
    axis limits to make visual comparison easier.
    """

    finished = Signal(bool, object)  # (success, dict[Path, bytes] | str)

    def __init__(
        self,
        samples: list[tuple[Path, pd.DataFrame]],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._samples = samples

    def generate_thumbnails(self) -> None:
        """Generate thumbnail PNG data for all samples."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            thumbnails: dict[Path, bytes] = {}

            # First pass: find global min/max for consistent axes
            global_time_min = float('inf')
            global_time_max = float('-inf')
            global_value_min = float('inf')
            global_value_max = float('-inf')

            for csv_path, df in self._samples:
                try:
                    time_values = df["time"].values
                    trace_values = df["value"].values
                    
                    if len(time_values) > 0:
                        global_time_min = min(global_time_min, np.min(time_values))
                        global_time_max = max(global_time_max, np.max(time_values))
                    
                    if len(trace_values) > 0:
                        global_value_min = min(global_value_min, np.min(trace_values))
                        global_value_max = max(global_value_max, np.max(trace_values))
                        
                except Exception as e:
                    logger.warning("Failed to scan %s for global limits: %s", csv_path, e)

            # Add small padding to the limits
            time_padding = (global_time_max - global_time_min) * 0.02 if global_time_max > global_time_min else 1.0
            value_padding = (global_value_max - global_value_min) * 0.02 if global_value_max > global_value_min else 1.0
            global_time_min -= time_padding
            global_time_max += time_padding
            global_value_min -= value_padding
            global_value_max += value_padding

            # Second pass: generate thumbnails with consistent limits
            for csv_path, df in self._samples:
                try:
                    fig, ax = plt.subplots(figsize=(2, 1.5), dpi=100)

                    # Get cell IDs
                    cell_ids = df.index.unique().tolist()

                    # Plot individual traces in gray
                    for fov, cell in cell_ids:
                        cell_data = df.loc[(fov, cell)]
                        time_values = cell_data["time"].values
                        trace_values = cell_data["value"].values
                        ax.plot(
                            time_values,
                            trace_values,
                            color="gray",
                            alpha=0.2,
                            linewidth=0.5,
                        )

                    # Calculate and plot mean in red
                    if cell_ids:
                        all_frames = np.sort(df["frame"].unique())
                        n_frames = len(all_frames)
                        padded = np.full((len(cell_ids), n_frames), np.nan)

                        for i, (fov, cell) in enumerate(cell_ids):
                            cell_data = df.loc[(fov, cell)]
                            cell_frames = cell_data["frame"].values
                            cell_values = cell_data["value"].values
                            frame_indices = np.searchsorted(all_frames, cell_frames)
                            padded[i, frame_indices] = cell_values

                        mean_values = np.nanmean(padded, axis=0)
                        time_values = (
                            df.loc[df["frame"].isin(all_frames)]
                            .groupby("frame")["time"]
                            .first()
                            .values
                        )
                        ax.plot(time_values, mean_values, color="red", linewidth=1.5)

                    # Set consistent limits for all thumbnails
                    if global_time_max > global_time_min and global_value_max > global_value_min:
                        ax.set_xlim(global_time_min, global_time_max)
                        ax.set_ylim(global_value_min, global_value_max)

                    ax.set_xticks([])
                    ax.set_yticks([])
                    ax.spines["top"].set_visible(False)
                    ax.spines["right"].set_visible(False)
                    ax.spines["bottom"].set_visible(False)
                    ax.spines["left"].set_visible(False)

                    # Save to bytes
                    import io
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.02)
                    buf.seek(0)
                    thumbnails[csv_path] = buf.read()

                    plt.close(fig)

                except Exception as e:
                    logger.warning("Failed to generate thumbnail for %s: %s", csv_path, e)

            self.finished.emit(True, thumbnails)

        except Exception as e:
            logger.exception("Thumbnail generation failed")
            self.finished.emit(False, str(e))


class ComparisonPanel(QWidget):
    """Panel for comparing multiple sample CSV files.

    This panel displays a grid of sample thumbnails loaded from a folder.
    Users can double-click a sample to emit a signal to open it in an analysis window.
    """

    # Signal emitted when user wants to open AnalysisWindow
    window_request = Signal(Path, object, object, float, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._status_manager = None
        self._samples: dict[Path, pd.DataFrame] = {}
        self._sample_cards: dict[Path, SampleCard] = {}
        self._frame_interval: float = 1 / 6
        self._time_mapping: dict[int, float] | None = None
        self._thumbnail_worker: WorkerHandle | None = None

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Controls group
        controls_group = self._build_controls_group()
        layout.addWidget(controls_group)

        # Samples group with scrollable thumbnail grid
        samples_group = QGroupBox("Samples")
        samples_layout = QVBoxLayout(samples_group)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll_area.setWidget(self._grid_widget)

        samples_layout.addWidget(self._scroll_area)
        layout.addWidget(samples_group)

    def _build_controls_group(self) -> QGroupBox:
        group = QGroupBox("Sample Selection")
        layout = QVBoxLayout(group)

        # First row: Load folder
        top_row = QHBoxLayout()
        self._load_folder_button = QPushButton("Load Folder...")
        top_row.addWidget(self._load_folder_button)
        top_row.addStretch()
        layout.addLayout(top_row)

        # Second row: Frame interval and time mapping
        settings_row = QHBoxLayout()
        
        # Frame interval input
        settings_row.addWidget(QLabel("Frame interval:"))
        self._frame_interval_edit = QLineEdit()
        self._frame_interval_edit.setText(f"{self._frame_interval:.4f}")
        self._frame_interval_edit.setFixedWidth(80)
        self._frame_interval_edit.setToolTip(
            "Time interval between frames in hours (e.g., 0.1667 for 10 min)"
        )
        settings_row.addWidget(self._frame_interval_edit)
        settings_row.addWidget(QLabel("hours"))

        # Time mapping
        self._time_mapping_label = QLabel("Time mapping: (none)")
        settings_row.addWidget(self._time_mapping_label)
        settings_row.addStretch()
        self._load_mapping_button = QPushButton("Load...")
        self._load_mapping_button.setFixedWidth(60)
        self._load_mapping_button.setToolTip("Load CSV with frame,time columns for non-equidistant time points")
        settings_row.addWidget(self._load_mapping_button)
        self._clear_mapping_button = QPushButton("Clear")
        self._clear_mapping_button.setFixedWidth(50)
        self._clear_mapping_button.setEnabled(False)
        settings_row.addWidget(self._clear_mapping_button)

        layout.addLayout(settings_row)

        return group

    def _connect_signals(self) -> None:
        self._load_folder_button.clicked.connect(self._on_load_folder_clicked)
        self._load_mapping_button.clicked.connect(self._on_load_mapping_clicked)
        self._clear_mapping_button.clicked.connect(self._on_clear_mapping_clicked)

    def set_status_manager(self, status_manager) -> None:
        """Set the status manager for status updates."""
        self._status_manager = status_manager

    @Slot()
    def _on_load_folder_clicked(self) -> None:
        """Handle load folder button click."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with CSV Files",
            str(DEFAULT_DIR),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if folder_path:
            self._load_folder(Path(folder_path))

    def _clear_all_samples(self) -> None:
        """Clear all samples."""
        # Clear samples and cards
        self._samples.clear()
        self._sample_cards.clear()
        self._clear_grid()

    def _clear_grid(self) -> None:
        """Remove all cards from the grid."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _load_folder(self, folder_path: Path) -> None:
        """Load all CSV files from a folder."""
        # Clear existing samples
        self._clear_all_samples()

        # Get frame interval
        try:
            self._frame_interval = float(self._frame_interval_edit.text())
        except ValueError:
            self._frame_interval = 1 / 6

        # Discover CSV files (excluding fitted and traces files)
        csv_files = [
            f
            for f in folder_path.glob("*.csv")
            if "_fitted" not in f.name and "_traces" not in f.name
        ]

        if not csv_files:
            if self._status_manager:
                self._status_manager.show_message(f"No CSV files found in {folder_path}")
            return

        logger.info("Loading %d CSV files from %s", len(csv_files), folder_path)

        # Clear existing data (already done if prompting, but keep for safety)
        self._clear_grid()
        self._samples.clear()
        self._sample_cards.clear()

        # Load each CSV file
        samples_to_thumbnail: list[tuple[Path, pd.DataFrame]] = []
        for csv_file in sorted(csv_files):
            try:
                df = load_analysis_csv(
                    csv_file, 
                    frame_interval=self._frame_interval,
                    time_mapping=self._time_mapping,
                )
                self._samples[csv_file] = df
                cell_count = len(df.index.unique())
                samples_to_thumbnail.append((csv_file, df))

                # Create card
                card = SampleCard(csv_file, cell_count, self)
                card.double_clicked.connect(self._on_sample_double_clicked)
                self._sample_cards[csv_file] = card

                # Add to grid
                idx = len(self._sample_cards) - 1
                row = idx // GRID_COLUMNS
                col = idx % GRID_COLUMNS
                self._grid_layout.addWidget(card, row, col)

                logger.info("Loaded %s (%d cells)", csv_file.name, cell_count)

            except Exception as e:
                logger.warning("Failed to load %s: %s", csv_file, e)

        if self._status_manager:
            self._status_manager.show_message(
                f"Loaded {len(self._samples)} samples from {folder_path.name}"
            )

        # Generate thumbnails in background
        if samples_to_thumbnail:
            self._start_thumbnail_generation(samples_to_thumbnail)

    @Slot()
    def _on_load_mapping_clicked(self) -> None:
        """Handle load time mapping button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Time Mapping CSV",
            str(DEFAULT_DIR),
            "CSV Files (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._load_time_mapping(Path(file_path))

    @Slot()
    def _on_clear_mapping_clicked(self) -> None:
        """Handle clear time mapping button click."""
        self._time_mapping = None
        self._time_mapping_label.setText("Time mapping: (none)")
        self._clear_mapping_button.setEnabled(False)
        self._frame_interval_edit.setEnabled(True)
        logger.info("Time mapping cleared")

    def _load_time_mapping(self, path: Path) -> None:
        """Load time mapping from CSV file with frame,time columns."""
        try:
            df = pd.read_csv(path)
            if "frame" not in df.columns or "time" not in df.columns:
                logger.error("Time mapping CSV must have 'frame' and 'time' columns")
                if self._status_manager:
                    self._status_manager.show_message(
                        "Time mapping CSV must have 'frame' and 'time' columns"
                    )
                return
            self._time_mapping = dict(
                zip(df["frame"].astype(int), df["time"].astype(float))
            )
            self._time_mapping_label.setText(f"Time mapping: {path.name}")
            self._clear_mapping_button.setEnabled(True)
            self._frame_interval_edit.setEnabled(False)
            logger.info(
                "Loaded time mapping from %s (%d entries)", path, len(self._time_mapping)
            )
            if self._status_manager:
                self._status_manager.show_message(
                    f"Loaded time mapping from {path.name} ({len(self._time_mapping)} entries)"
                )
        except Exception as e:
            logger.error("Failed to load time mapping: %s", e)
            if self._status_manager:
                self._status_manager.show_message(f"Failed to load time mapping: {e}")

    def _start_thumbnail_generation(
        self, samples: list[tuple[Path, pd.DataFrame]]
    ) -> None:
        """Start background thumbnail generation."""
        worker = ThumbnailWorker(samples)
        worker.finished.connect(self._on_thumbnails_finished)

        self._thumbnail_worker = start_worker(
            worker,
            start_method="generate_thumbnails",
            finished_callback=lambda: setattr(self, "_thumbnail_worker", None),
        )

    @Slot(bool, object)
    def _on_thumbnails_finished(self, success: bool, result: object) -> None:
        """Handle thumbnail generation completion."""
        if success and isinstance(result, dict):
            for csv_path, png_data in result.items():
                if csv_path in self._sample_cards:
                    pixmap = QPixmap()
                    pixmap.loadFromData(png_data)
                    self._sample_cards[csv_path].set_thumbnail(pixmap)
            logger.info("Generated %d thumbnails", len(result))
        else:
            logger.warning("Thumbnail generation failed: %s", result)

    @Slot(Path)
    def _on_sample_double_clicked(self, csv_path: Path) -> None:
        """Handle double-click on a sample card."""
        # Get data
        df = self._samples.get(csv_path)
        if df is None:
            logger.warning("No data found for %s", csv_path)
            return

        # Find fitted results if they exist
        fitted_path = self._find_fitted_csv(csv_path)

        # Emit signal to request window opening
        self.window_request.emit(
            csv_path,
            df,
            fitted_path,
            self._frame_interval,
            self._time_mapping
        )

    def _find_fitted_csv(self, csv_path: Path) -> Path | None:
        """Find matching fitted CSV file if exists."""
        parent = csv_path.parent
        stem = csv_path.stem
        for fitted_file in parent.glob(f"{stem}_fitted_*.csv"):
            return fitted_file
        return None
