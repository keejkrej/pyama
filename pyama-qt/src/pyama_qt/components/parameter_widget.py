"""
Simplified ParameterWidget with checkbox to toggle table visibility and editability,
set_table to populate from DataFrame, and get_table to return DataFrame.
The widget does not store the DataFrame internally.
"""

import pandas as pd
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
)
from PySide6.QtCore import Qt, Property, Signal


class ParameterWidget(QWidget):
    """A widget that displays editable parameters in a table.

    Usage:
    - Use set_table(df) to populate the table from a DataFrame.
      The DataFrame should have parameter names as index OR include a 'name' column.
      All other columns are treated as fields (e.g., value, min, max...).
    - Use get_table() to retrieve the current table contents as a DataFrame.
    - The checkbox toggles table visibility and editability.
    """

    tableChanged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.build()
        self.bind()

    def build(self):
        layout = QVBoxLayout(self)

        self._manual_params = QCheckBox("Set parameters manually")
        layout.addWidget(self._manual_params)

        self._table = QTableWidget(0, 0, self)
        layout.addWidget(self._table)

        self._on_toggle(False)  # initialize disabled state

    def bind(self):
        self._manual_params.stateChanged.connect(self._on_toggle)

    @Property(pd.DataFrame, notify=tableChanged)
    def table(self) -> pd.DataFrame:
        """Return the current table contents as a DataFrame."""
        param_names = []
        fields = []
        col_count = self._table.columnCount()
        if col_count > 1:
            # Get field names from headers (skip 'Parameter')
            for c in range(1, col_count):
                header_item = self._table.horizontalHeaderItem(c)
                fields.append(header_item.text() if header_item else f"field_{c}")

        rows = []
        for r in range(self._table.rowCount()):
            pname_item = self._table.item(r, 0)
            pname = pname_item.text() if pname_item else f"param_{r}"
            param_names.append(pname)
            row_dict = {}
            for c, field in enumerate(fields, start=1):
                it = self._table.item(r, c)
                text = it.text() if it else ""
                row_dict[field] = self._coerce(text)
            rows.append(row_dict)

        if not param_names:
            return pd.DataFrame()

        df = pd.DataFrame(rows, index=param_names, columns=fields)
        return df

    @table.setter
    def table(self, df: pd.DataFrame) -> None:
        """Populate the table from a pandas DataFrame.

        - If a 'name' column exists, it is used as the row index and not shown as a field.
        - Otherwise, the DataFrame's index is used for parameter names.
        - All remaining columns are fields.
        """
        if df is None or df.empty:
            # Clear the table
            self._rebuild_table([], [], pd.DataFrame())
            return

        df_local = df.copy()
        if "name" in df_local.columns:
            df_local = df_local.set_index("name")
        # Normalize index to strings
        df_local.index = df_local.index.map(lambda x: str(x))

        param_names = list(df_local.index)
        fields = list(df_local.columns)

        self._rebuild_table(param_names, fields, df_local)
        self.tableChanged.emit()

    def _rebuild_table(
        self, param_names: list[str], fields: list[str], df: pd.DataFrame
    ) -> None:
        # Block signals during rebuild
        self._table.blockSignals(True)
        try:
            # Define columns: first column is 'Parameter' (name), others are fields
            n_rows = len(param_names)
            n_cols = 1 + len(fields)
            self._table.clear()
            self._table.setRowCount(n_rows)
            self._table.setColumnCount(n_cols)

            headers = ["Parameter"] + fields
            self._table.setHorizontalHeaderLabels(headers)

            for r, pname in enumerate(param_names):
                # Name column (read-only)
                name_item = QTableWidgetItem(pname)
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self._table.setItem(r, 0, name_item)

                # Field value columns
                for c, field in enumerate(fields, start=1):
                    val = None
                    if pname in df.index and field in df.columns:
                        val = df.loc[pname, field]
                    text = "" if pd.isna(val) else str(val)
                    item = QTableWidgetItem(text)
                    self._table.setItem(r, c, item)
        finally:
            self._table.blockSignals(False)

    def _coerce(self, text: str):
        # Try to coerce to int or float if possible; fallback to string
        if text is None or text == "":
            return None
        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except ValueError:
            return text

    def _on_toggle(self, enabled):
        self._table.setVisible(enabled)
        if enabled:
            self._table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        else:
            self._table.clearSelection()
            self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import (
        QApplication,
        QMainWindow,
        QWidget,
        QVBoxLayout,
        QPushButton,
    )

    # Create a test DataFrame
    test_df = pd.DataFrame(
        {
            "name": ["param1", "param2", "param3"],
            "value": [1.0, 2.5, 3.0],
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 10.0, 10.0],
        }
    )

    app = QApplication(sys.argv)
    main_window = QMainWindow()
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)

    # Create button outside the widget
    get_button = QPushButton("Get Table")
    get_button.clicked.connect(lambda: print(widget.table))
    layout.addWidget(get_button)

    # Create the ParameterWidget
    widget = ParameterWidget()
    widget.table = test_df
    layout.addWidget(widget)

    main_window.setCentralWidget(central_widget)
    main_window.show()
    sys.exit(app.exec())
