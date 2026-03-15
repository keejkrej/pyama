"""Cross-sample comparison panel for statistics results."""

import pandas as pd
from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pyama_pro.components.mpl_canvas import MplCanvas


class StatisticsComparisonPanel(QWidget):
    """Grouped distribution and summary view across all samples."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._results_df: pd.DataFrame | None = None
        self._mode: str = "auc"
        self._selected_metric: str | None = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Sample Comparison")
        group_layout = QVBoxLayout(group)

        metric_row = QHBoxLayout()
        metric_row.addWidget(QLabel("Metric:"))
        self._metric_combo = QComboBox()
        metric_row.addWidget(self._metric_combo)
        group_layout.addLayout(metric_row)

        self._boxplot_canvas = MplCanvas(self)
        group_layout.addWidget(self._boxplot_canvas)

        self._summary_table = QTableWidget(0, 6)
        self._summary_table.setHorizontalHeaderLabels(
            ["Sample", "N", "Mean", "Std", "Median", "IQR"]
        )
        header = self._summary_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._summary_table.verticalHeader().setVisible(False)
        group_layout.addWidget(self._summary_table)

        layout.addWidget(group)

    def _connect_signals(self) -> None:
        self._metric_combo.currentTextChanged.connect(self._on_metric_changed)

    def clear(self) -> None:
        self._results_df = None
        self._selected_metric = None
        self._metric_combo.clear()
        self._boxplot_canvas.clear()
        self._summary_table.setRowCount(0)

    def set_results(self, results_df: pd.DataFrame, mode: str) -> None:
        self._results_df = results_df
        self._mode = mode

        preferred_metric = "auc" if mode == "auc" else "onset_time"
        available_metrics = self._available_metrics(results_df)

        self._metric_combo.blockSignals(True)
        self._metric_combo.clear()
        self._metric_combo.addItems(available_metrics)
        self._metric_combo.blockSignals(False)

        if preferred_metric in available_metrics:
            self._metric_combo.setCurrentText(preferred_metric)
            self._selected_metric = preferred_metric
        elif available_metrics:
            self._selected_metric = available_metrics[0]
            self._metric_combo.setCurrentIndex(0)
        else:
            self._selected_metric = None

        self._update_views()

    def _available_metrics(self, results_df: pd.DataFrame) -> list[str]:
        metadata_columns = {
            "sample",
            "fov",
            "cell",
            "analysis_mode",
            "success",
            "n_points",
            "fit_window_hours",
            "normalization_mode",
            "source_intensity_file",
            "source_area_file",
            "time_start",
            "time_end",
        }
        metrics = []
        for column in results_df.columns:
            if column in metadata_columns:
                continue
            if pd.to_numeric(results_df[column], errors="coerce").notna().any():
                metrics.append(column)
        return metrics

    @Slot(str)
    def _on_metric_changed(self, metric_name: str) -> None:
        if metric_name:
            self._selected_metric = metric_name
            self._update_views()

    def _update_views(self) -> None:
        if self._results_df is None or not self._selected_metric:
            self.clear()
            return

        grouped_values: dict[str, list[float]] = {}
        summary_rows: list[tuple[str, int, float, float, float, float]] = []

        for sample_name, sample_df in self._results_df.groupby("sample", sort=True):
            values = pd.to_numeric(
                sample_df[self._selected_metric], errors="coerce"
            ).dropna()
            if "success" in sample_df.columns:
                success_mask = sample_df["success"].fillna(False).astype(bool)
                values = pd.to_numeric(
                    sample_df.loc[success_mask, self._selected_metric], errors="coerce"
                ).dropna()

            grouped_values[sample_name] = values.tolist()
            if values.empty:
                continue

            q1 = float(values.quantile(0.25))
            q3 = float(values.quantile(0.75))
            summary_rows.append(
                (
                    sample_name,
                    int(len(values)),
                    float(values.mean()),
                    float(values.std(ddof=0)),
                    float(values.median()),
                    q3 - q1,
                )
            )

        self._boxplot_canvas.plot_boxplot(
            grouped_values,
            title=f"Comparison of {self._selected_metric}",
            x_label="Sample",
            y_label=self._selected_metric,
        )

        self._summary_table.setRowCount(len(summary_rows))
        for row_index, row_values in enumerate(summary_rows):
            for col_index, value in enumerate(row_values):
                if isinstance(value, float):
                    text = f"{value:.3f}"
                else:
                    text = str(value)
                self._summary_table.setItem(
                    row_index, col_index, QTableWidgetItem(text)
                )
