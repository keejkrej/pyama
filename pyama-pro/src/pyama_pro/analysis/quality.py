"""Fitting quality inspection panel for the analysis tab.

This module provides the QualityPanel widget which displays fitting diagnostics
including trace visualization, FOV-based trace selection, and quality statistics.
"""

import logging

import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama_core.analysis.fitting import analyze_fitting_quality
from pyama_core.analysis.models import get_model
from pyama_pro.components.mpl_canvas import MplCanvas

logger = logging.getLogger(__name__)


class QualityPanel(QWidget):
    """Middle panel visualising fitting diagnostics and individual fits.

    This panel provides an interface for inspecting the quality of model
    fits. It includes:

    - **Trace visualization**: Shows raw data with fitted curves for selected cells
    - **FOV-based pagination**: Groups traces by FOV (field of view) for easy navigation
    - **Quality statistics**: Displays good/mid/bad fitting percentages based on R² thresholds
    - **Color-coded trace list**: Visual indicators for fitting quality:
      - Green: R² > 0.9 (good)
      - Orange: 0.7 < R² ≤ 0.9 (mid)
      - Red: R² ≤ 0.7 (bad)

    The panel expects cell IDs in the format `fov_xxx_cell_yyy` for FOV grouping.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    cell_visualized = Signal(str)  # Emitted when a cell is visualized (cell ID)
    fitting_completed = Signal(object)  # Emitted when fitting completes (pd.DataFrame)

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, *args, **kwargs) -> None:
        """Initialize the quality panel.

        Args:
            *args: Positional arguments passed to parent QWidget
            **kwargs: Keyword arguments passed to parent QWidget
        """
        super().__init__(*args, **kwargs)
        self._build_ui()
        self._connect_signals()

        # State
        self._results_df: pd.DataFrame | None = None
        self._raw_data: pd.DataFrame | None = None
        self._selected_cell: str | None = None
        self._cell_ids: list[str] = []
        self._fov_groups: dict[int, list[str]] = {}  # FOV -> list of cell IDs
        self._fov_list: list[int] = []  # Ordered list of FOVs
        self._current_page = 0

        # UI Components
        self._trace_group: QGroupBox | None = None
        self._selection_group: QGroupBox | None = None

    # ------------------------------------------------------------------------
    # UI SETUP
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout.

        Creates a vertical layout with two main groups:
        1. Trace visualization group for displaying individual cell traces
        2. Trace selection group with paginated list and statistics
        """
        layout = QVBoxLayout(self)

        # Add trace visualization group
        self._trace_group = self._build_trace_group()
        layout.addWidget(self._trace_group)

        # Add trace selection group
        self._selection_group = self._build_selection_group()
        layout.addWidget(self._selection_group)

    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers.

        Sets up the signal/slot connections for trace selection and pagination.
        """
        self._trace_list.itemClicked.connect(self._on_list_item_clicked)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)

    def _build_trace_group(self) -> QGroupBox:
        """Build the trace visualization group.

        Returns:
            QGroupBox containing the trace plot canvas
        """
        group = QGroupBox("Fitted Traces")
        layout = QVBoxLayout(group)

        self._trace_canvas = MplCanvas(self)
        layout.addWidget(self._trace_canvas)

        return group

    def _build_selection_group(self) -> QGroupBox:
        """Build the trace selection group.

        Returns:
            QGroupBox containing statistics label, trace list, and pagination controls
        """
        group = QGroupBox("Trace Selection")
        layout = QVBoxLayout(group)

        # Statistics label
        self._stats_label = QLabel("Good: 0%, Mid: 0%, Bad: 0%")
        self._stats_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self._stats_label)

        # List widget for traces
        self._trace_list = QListWidget()
        self._trace_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._trace_list)

        # Pagination controls
        pagination_row = QHBoxLayout()
        self._page_label = QLabel("Page 1 of 1")
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._prev_button)
        pagination_row.addWidget(self._next_button)
        layout.addLayout(pagination_row)

        return group

    # ------------------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------------------
    def _extract_fov_from_cell_id(self, cell_id: str) -> int | None:
        """Extract FOV number from cell ID in format 'fov_xxx_cell_yyy'.

        Args:
            cell_id: Cell ID string

        Returns:
            FOV number or None if parsing fails
        """
        if not isinstance(cell_id, str):
            return None

        parts = cell_id.split("_")
        if len(parts) >= 2 and parts[0] == "fov":
            try:
                return int(parts[1])
            except ValueError:
                return None
        return None

    # ------------------------------------------------------------------------
    # PUBLIC SLOTS
    # ------------------------------------------------------------------------
    @Slot(object)
    def on_fitting_completed(self, results_df: pd.DataFrame) -> None:
        """Handle fitting completion event.

        Args:
            results_df: DataFrame containing fitting results
        """
        self.set_results(results_df)

    @Slot(object)
    def on_raw_data_changed(self, df: pd.DataFrame) -> None:
        """Handle raw data change event.

        Args:
            df: DataFrame containing raw trace data
        """
        self._raw_data = df
        if self._selected_cell:
            self._update_trace_plot(self._selected_cell)

    @Slot(object)
    def on_fitted_results_changed(self, results_df: pd.DataFrame) -> None:
        """Handle fitted results change event.

        Args:
            results_df: DataFrame containing fitted results
        """
        self.set_results(results_df)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, item: QListWidgetItem) -> None:
        """Handle click on list item.

        Args:
            item: The clicked list item
        """
        cell_id = item.data(Qt.ItemDataRole.UserRole)
        if cell_id:
            logger.debug(f"List item clicked: {cell_id}")
            self._selected_cell = cell_id
            self._update_trace_plot(cell_id)
            self.cell_visualized.emit(cell_id)

    @Slot()
    def _on_prev_page(self) -> None:
        """Handle previous page button click."""
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination()
            self._populate_table()

    @Slot()
    def _on_next_page(self) -> None:
        """Handle next page button click."""
        total_pages = max(1, len(self._fov_list))
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_pagination()
            self._populate_table()

    # ------------------------------------------------------------------------
    # INTERNAL LOGIC
    # ------------------------------------------------------------------------
    def set_results(self, df: pd.DataFrame) -> None:
        """Set the results DataFrame and update UI.

        Args:
            df: DataFrame containing fitting results
        """
        self._results_df = df
        if df is None or df.empty:
            self.clear()
            return

        # Extract cell IDs from results and group by FOV
        if "cell_id" in df.columns:
            self._cell_ids = df["cell_id"].astype(str).tolist()

            # Group cells by FOV
            self._fov_groups = {}
            for cell_id in self._cell_ids:
                fov = self._extract_fov_from_cell_id(cell_id)
                if fov is not None:
                    if fov not in self._fov_groups:
                        self._fov_groups[fov] = []
                    self._fov_groups[fov].append(cell_id)

            # Sort cells within each FOV
            for fov in self._fov_groups:
                self._fov_groups[fov].sort(
                    key=lambda x: int(x.split("_")[-1])
                    if x.split("_")[-1].isdigit()
                    else 0
                )

            # Create ordered list of FOVs
            self._fov_list = sorted(self._fov_groups.keys())
        else:
            self._cell_ids = []
            self._fov_groups = {}
            self._fov_list = []

        self._current_page = 0
        self._update_pagination()
        self._populate_table()
        self._update_statistics()

    def clear(self) -> None:
        """Clear all data and reset UI state."""
        self._results_df = None
        self._raw_data = None
        self._selected_cell = None
        self._cell_ids = []
        self._fov_groups = {}
        self._fov_list = []
        self._current_page = 0
        self._trace_canvas.clear()
        self._trace_list.clear()
        self._update_pagination()
        self._update_statistics()

    def _update_statistics(self) -> None:
        """Update the fitting statistics label."""
        if self._results_df is None or "r_squared" not in self._results_df.columns:
            self._stats_label.setText("Good: 0%, Mid: 0%, Bad: 0%")
            return

        quality_metrics = analyze_fitting_quality(self._results_df)
        if not quality_metrics:
            self._stats_label.setText("Good: 0%, Mid: 0%, Bad: 0%")
            return

        good_pct = quality_metrics["good_percentage"]
        fair_pct = quality_metrics["fair_percentage"]
        poor_pct = quality_metrics["poor_percentage"]

        self._stats_label.setText(
            f"Good: {good_pct:.1f}%, Mid: {fair_pct:.1f}%, Bad: {poor_pct:.1f}%"
        )

    def _update_pagination(self) -> None:
        """Update pagination controls."""
        total_pages = max(1, len(self._fov_list))
        current_fov = (
            self._fov_list[self._current_page]
            if self._current_page < len(self._fov_list)
            else None
        )
        cell_count = (
            len(self._fov_groups.get(current_fov, [])) if current_fov is not None else 0
        )

        if current_fov is not None:
            self._page_label.setText(
                f"FOV {current_fov} ({cell_count} cells) - Page {self._current_page + 1} of {total_pages}"
            )
        else:
            self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < total_pages - 1)

    def _populate_table(self) -> None:
        """Populate the list widget with visible traces."""
        trace_ids = self._visible_trace_ids()
        self._trace_list.blockSignals(True)
        self._trace_list.clear()

        for cell_id in trace_ids:
            # Extract cell number from cell_id for display
            cell_display = cell_id
            if "_cell_" in cell_id:
                cell_display = cell_id.split("_cell_")[-1]

            item = QListWidgetItem(f"Cell {cell_display}")
            item.setData(Qt.ItemDataRole.UserRole, cell_id)

            # Get R² value for color coding
            if self._results_df is not None:
                result_row = self._results_df[self._results_df["cell_id"] == cell_id]
                if result_row.empty:
                    try:
                        cell_id_int = int(cell_id)
                        result_row = self._results_df[
                            self._results_df["cell_id"] == cell_id_int
                        ]
                    except ValueError:
                        pass

                if not result_row.empty and "r_squared" in result_row.columns:
                    r_squared = result_row.iloc[0]["r_squared"]
                    if pd.notna(r_squared):
                        if r_squared > 0.9:
                            color = QColor("green")
                        elif r_squared > 0.7:
                            color = QColor("orange")
                        else:
                            color = QColor("red")
                        item.setForeground(color)

            self._trace_list.addItem(item)

        self._trace_list.blockSignals(False)

    def _visible_trace_ids(self) -> list[str]:
        """Get the list of trace IDs visible on the current page (current FOV).

        Returns:
            List of trace IDs visible on the current page (all cells from current FOV)
        """
        if self._current_page < len(self._fov_list):
            current_fov = self._fov_list[self._current_page]
            return self._fov_groups.get(current_fov, [])
        return []

    def _update_trace_plot(self, cell_id: str) -> None:
        """Update the trace plot with raw data and fitted curve.

        Args:
            cell_id: ID of the cell to visualize
        """
        if self._raw_data is None or cell_id not in self._raw_data.columns:
            self._trace_canvas.clear()
            return

        # Get the raw trace data directly from DataFrame
        time_data = self._raw_data.index.values.astype(np.float64)
        trace_data = self._raw_data[cell_id].values.astype(np.float64)

        # Prepare to get fitted parameters if available
        fitted_params = None
        model_type = None
        success = None

        if self._results_df is not None:
            # Find the corresponding row in results for this cell_id
            # Try both string and integer matching for backward compatibility
            result_row = self._results_df[self._results_df["cell_id"] == cell_id]

            # If no match with string, try converting to int for backward compatibility
            if result_row.empty:
                try:
                    cell_id_int = int(cell_id)
                    result_row = self._results_df[
                        self._results_df["cell_id"] == cell_id_int
                    ]
                except ValueError:
                    pass

            if not result_row.empty:
                result_row = result_row.iloc[0]
                if "model_type" in result_row:
                    model_type = result_row["model_type"]
                if "success" in result_row:
                    success = result_row["success"]

                # Get fitted parameters (excluding special columns)
                special_cols = {"cell_id", "model_type", "success", "r_squared"}
                fitted_params = {
                    col: result_row[col]
                    for col in result_row.index
                    if col not in special_cols and pd.notna(result_row[col])
                }

        # Create the plot
        lines_data = []
        styles_data = []

        # Plot raw data
        lines_data.append((time_data, trace_data))
        styles_data.append(
            {"color": "blue", "alpha": 0.7, "label": cell_id, "linewidth": 1}
        )

        # Plot fitted curve if parameters are available and fitting was successful
        if fitted_params and model_type and success:
            try:
                model = get_model(model_type)
                params_obj = model.Params(**fitted_params)
                fitted_trace = model.eval(time_data, params_obj)

                lines_data.append((time_data, fitted_trace))
                styles_data.append(
                    {"color": "red", "alpha": 0.8, "label": "Fitted", "linewidth": 2}
                )
            except Exception as e:
                logger.warning(
                    f"Could not generate fitted curve for cell {cell_id}: {e}"
                )

        self._render_trace_plot_internal(
            lines_data,
            styles_data,
            x_label="Time (hours)",
            y_label="Intensity",
        )

    def _render_trace_plot_internal(
        self,
        lines_data: list,
        styles_data: list,
        *,
        x_label: str = "Time (hours)",
        y_label: str = "Intensity",
    ) -> None:
        """Internal method to render the trace plot.

        Args:
            lines_data: List of line data tuples (x, y)
            styles_data: List of style dictionaries
            x_label: X-axis label
            y_label: Y-axis label
        """
        self._trace_canvas.plot_lines(
            lines_data,
            styles_data,
            x_label=x_label,
            y_label=y_label,
        )
