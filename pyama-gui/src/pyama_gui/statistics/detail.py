"""Per-sample trace detail panel for statistics results."""

import pandas as pd
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyama.tasks import evaluate_onset_trace
from pyama_gui.components.mpl_canvas import MplCanvas


class StatisticsDetailPanel(QWidget):
    """Per-sample detail view for statistics results."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._results_df: pd.DataFrame | None = None
        self._traces_by_sample: dict[str, pd.DataFrame] = {}
        self._mode: str = "auc"
        self._normalize_by_area = False
        self._selected_sample: str | None = None
        self._selected_cell: tuple[int, int] | None = None
        self._fov_groups: dict[int, list[tuple[int, int]]] = {}
        self._fov_list: list[int] = []
        self._current_page = 0
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Sample Detail")
        group_layout = QVBoxLayout(group)

        sample_row = QHBoxLayout()
        sample_row.addWidget(QLabel("Sample:"))
        self._sample_combo = QComboBox()
        sample_row.addWidget(self._sample_combo)
        group_layout.addLayout(sample_row)

        self._stats_label = QLabel("Load and run a statistics job to inspect traces.")
        self._stats_label.setWordWrap(True)
        group_layout.addWidget(self._stats_label)

        self._trace_canvas = MplCanvas(self)
        group_layout.addWidget(self._trace_canvas)

        self._trace_list = QListWidget()
        group_layout.addWidget(self._trace_list)

        pagination_row = QHBoxLayout()
        self._page_label = QLabel("Page 1 of 1")
        self._prev_button = QPushButton("Previous")
        self._next_button = QPushButton("Next")
        pagination_row.addWidget(self._page_label)
        pagination_row.addWidget(self._prev_button)
        pagination_row.addWidget(self._next_button)
        group_layout.addLayout(pagination_row)

        layout.addWidget(group)

    def _connect_signals(self) -> None:
        self._sample_combo.currentTextChanged.connect(self._on_sample_changed)
        self._trace_list.itemClicked.connect(self._on_list_item_clicked)
        self._prev_button.clicked.connect(self._on_prev_page)
        self._next_button.clicked.connect(self._on_next_page)

    def clear(self) -> None:
        self._results_df = None
        self._traces_by_sample = {}
        self._selected_sample = None
        self._selected_cell = None
        self._fov_groups = {}
        self._fov_list = []
        self._current_page = 0
        self._sample_combo.clear()
        self._trace_list.clear()
        self._trace_canvas.clear()
        self._stats_label.setText("Load and run a statistics job to inspect traces.")
        self._update_pagination()

    def set_results(
        self,
        results_df: pd.DataFrame,
        traces_by_sample: dict[str, pd.DataFrame],
        mode: str,
        *,
        normalize_by_area: bool,
    ) -> None:
        self._results_df = results_df
        self._traces_by_sample = traces_by_sample
        self._mode = mode
        self._normalize_by_area = normalize_by_area

        sample_names = sorted(traces_by_sample.keys())
        self._sample_combo.blockSignals(True)
        self._sample_combo.clear()
        self._sample_combo.addItems(sample_names)
        self._sample_combo.blockSignals(False)

        if sample_names:
            self._sample_combo.setCurrentIndex(0)
            self._set_sample(sample_names[0])
        else:
            self.clear()

    @Slot(str)
    def _on_sample_changed(self, sample_name: str) -> None:
        if sample_name:
            self._set_sample(sample_name)

    def _set_sample(self, sample_name: str) -> None:
        self._selected_sample = sample_name
        self._selected_cell = None
        self._fov_groups = {}
        self._fov_list = []
        self._current_page = 0

        sample_results = self._sample_results()
        if sample_results is not None and not sample_results.empty:
            for _, row in sample_results.iterrows():
                fov = int(row["fov"])
                cell = int(row["cell"])
                self._fov_groups.setdefault(fov, []).append((fov, cell))
            for fov in self._fov_groups:
                self._fov_groups[fov].sort(key=lambda value: value[1])
            self._fov_list = sorted(self._fov_groups)

        self._update_statistics()
        self._update_pagination()
        self._populate_table()

        visible_ids = self._visible_trace_ids()
        if visible_ids:
            self._selected_cell = visible_ids[0]
            self._update_trace_plot(self._selected_cell)

    def _sample_results(self) -> pd.DataFrame | None:
        if self._results_df is None or self._selected_sample is None:
            return None
        return self._results_df[self._results_df["sample"] == self._selected_sample]

    def _update_statistics(self) -> None:
        sample_results = self._sample_results()
        if sample_results is None or sample_results.empty:
            self._stats_label.setText("No sample results available.")
            return

        success_count = int(sample_results["success"].fillna(False).sum())
        total_count = int(len(sample_results))
        metric_column = "auc" if self._mode == "auc" else "onset_time"
        metric_values = pd.to_numeric(
            sample_results[metric_column], errors="coerce"
        ).dropna()
        metric_text = (
            f"median {metric_column}={metric_values.median():.3f}"
            if not metric_values.empty
            else f"median {metric_column}=n/a"
        )
        self._stats_label.setText(
            f"Sample {self._selected_sample}: {success_count}/{total_count} successful, {metric_text}"
        )

    def _update_pagination(self) -> None:
        total_pages = max(1, len(self._fov_list))
        if self._current_page < len(self._fov_list):
            current_fov = self._fov_list[self._current_page]
            cell_count = len(self._fov_groups.get(current_fov, []))
            self._page_label.setText(
                f"FOV {current_fov} ({cell_count} cells) - Page {self._current_page + 1} of {total_pages}"
            )
        else:
            self._page_label.setText(f"Page {self._current_page + 1} of {total_pages}")

        self._prev_button.setEnabled(self._current_page > 0)
        self._next_button.setEnabled(self._current_page < total_pages - 1)

    def _visible_trace_ids(self) -> list[tuple[int, int]]:
        if self._current_page < len(self._fov_list):
            return self._fov_groups.get(self._fov_list[self._current_page], [])
        return []

    def _populate_table(self) -> None:
        trace_ids = self._visible_trace_ids()
        sample_results = self._sample_results()

        self._trace_list.blockSignals(True)
        self._trace_list.clear()
        for fov, cell in trace_ids:
            item = QListWidgetItem(f"Cell {cell}")
            item.setData(Qt.ItemDataRole.UserRole, (fov, cell))

            if sample_results is not None:
                row_df = sample_results[
                    (sample_results["fov"] == fov) & (sample_results["cell"] == cell)
                ]
                if not row_df.empty:
                    row = row_df.iloc[0]
                    item.setForeground(self._row_color(row))

            self._trace_list.addItem(item)
        self._trace_list.blockSignals(False)

    def _row_color(self, row: pd.Series) -> QColor:
        success = bool(row.get("success", False))
        if not success:
            return QColor("red")

        if self._mode == "onset_shifted_relu":
            r_squared = pd.to_numeric(
                pd.Series([row.get("r_squared")]), errors="coerce"
            ).iloc[0]
            if pd.isna(r_squared):
                return QColor("green")
            if r_squared > 0.9:
                return QColor("green")
            if r_squared > 0.7:
                return QColor("orange")
            return QColor("red")

        return QColor("green")

    @Slot(QListWidgetItem)
    def _on_list_item_clicked(self, item: QListWidgetItem) -> None:
        cell_id = item.data(Qt.ItemDataRole.UserRole)
        if cell_id:
            self._selected_cell = cell_id
            self._update_trace_plot(cell_id)

    @Slot()
    def _on_prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._update_pagination()
            self._populate_table()

    @Slot()
    def _on_next_page(self) -> None:
        total_pages = max(1, len(self._fov_list))
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_pagination()
            self._populate_table()

    def _update_trace_plot(self, cell_id: tuple[int, int]) -> None:
        if self._selected_sample is None:
            self._trace_canvas.clear()
            return

        trace_df = self._traces_by_sample.get(self._selected_sample)
        sample_results = self._sample_results()
        if trace_df is None or sample_results is None:
            self._trace_canvas.clear()
            return

        fov, cell = cell_id
        try:
            cell_df = trace_df.loc[(fov, cell)].sort_values("time")
        except KeyError:
            self._trace_canvas.clear()
            return

        time_values = cell_df["time"].to_numpy()
        trace_values = cell_df["value"].to_numpy()
        lines_data = [(time_values, trace_values)]
        styles_data = [
            {
                "color": "blue",
                "alpha": 0.8,
                "label": f"FOV {fov}, Cell {cell}",
                "linewidth": 1.5,
            }
        ]

        row_df = sample_results[
            (sample_results["fov"] == fov) & (sample_results["cell"] == cell)
        ]
        title = f"{self._selected_sample}: FOV {fov}, Cell {cell}"
        if not row_df.empty:
            row = row_df.iloc[0]
            if self._mode == "auc" and pd.notna(row.get("auc")):
                title = f"{title} (AUC={row['auc']:.3f})"
            if (
                self._mode == "onset_shifted_relu"
                and bool(row.get("success", False))
                and pd.notna(row.get("onset_time"))
                and pd.notna(row.get("slope"))
                and pd.notna(row.get("offset"))
            ):
                fit_window_hours = float(
                    pd.to_numeric(
                        pd.Series([row.get("fit_window_hours", time_values.max())]),
                        errors="coerce",
                    ).iloc[0]
                )
                fit_mask = pd.notna(time_values) & (time_values <= fit_window_hours)
                fit_time_values = time_values[fit_mask]
                fitted_trace = evaluate_onset_trace(
                    fit_time_values,
                    float(row["onset_time"]),
                    float(row["slope"]),
                    float(row["offset"]),
                )
                lines_data.append((fit_time_values, fitted_trace))
                label = "Shifted ReLU"
                if pd.notna(row.get("r_squared")):
                    label = f"{label} (R²={row['r_squared']:.3f})"
                styles_data.append(
                    {
                        "color": "red",
                        "alpha": 0.8,
                        "label": label,
                        "linewidth": 2.0,
                    }
                )

        self._trace_canvas.plot_lines(
            lines_data,
            styles_data,
            title=title,
            x_label="Time (hours)",
            y_label=(
                "Normalized intensity / area"
                if self._normalize_by_area
                else "Intensity total"
            ),
        )
