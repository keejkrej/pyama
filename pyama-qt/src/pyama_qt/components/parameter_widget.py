import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)


class ParameterModel(QAbstractTableModel):
    """Qt model exposing parameters as a table."""

    def __init__(self, df: pd.DataFrame) -> None:
        super().__init__()
        self._df: pd.DataFrame = df.copy(deep=True)
        self._manual_mode: bool = False

    # Qt model overrides --------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        # if parent and parent.isValid():
        #     return 0
        return len(self._df.index)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        # if parent and parent.isValid():
        #     return 0
        return len(self._df.columns)

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> int | float | str | None:
        if not index or not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return None

        try:
            value = self._df.iloc[row, col]
            print(value)
            return int(value) if pd.notna(value) else None
        except (IndexError, ValueError):
            return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._df.columns[section])
            elif orientation == Qt.Orientation.Vertical:
                return str(self._df.index[section])
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index or not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if self._manual_mode:
            return (
                Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsEditable
            )
        else:
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def setData(
        self,
        index: QModelIndex,
        value: int | float | str,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if not index or not index.isValid():
            return False
        if role != Qt.ItemDataRole.EditRole:
            return False
        row = index.row()
        col = index.column()
        try:
            self._df.iloc[row, col] = value
        except (IndexError, ValueError):
            return False
        self.dataChanged.emit(index, index, [role])
        return True

    # Public surface -----------------------------------------------------
    def set_manual_mode(self, enabled: bool) -> None:
        if self._manual_mode == enabled:
            return
        self._manual_mode = enabled


class ParameterView(QWidget):
    """View exposing manual toggle and table widget."""

    manual_mode_toggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._manual_checkbox = QCheckBox("Set parameters manually", self)
        layout.addWidget(self._manual_checkbox)

        self._table = QTableView(self)
        layout.addWidget(self._table, 1)

        self._manual_checkbox.stateChanged.connect(self._on_checkbox_changed)

    def _on_checkbox_changed(self, state: int) -> None:
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
            self._table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        else:
            self._table.clearSelection()
            self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.manual_mode_toggled.emit(enabled)

    def set_model(self, model: ParameterModel) -> None:
        self._model = model
        self._table.setModel(model)


class ParameterController(QObject):
    """Connects the Qt view with the table model."""

    def __init__(self, view: ParameterView, model: ParameterModel) -> None:
        super().__init__(view)
        self._view = view
        self._model = model

        self._view.set_model(self._model)
        self._view.manual_mode_toggled.connect(self._model.set_manual_mode)
        self._model.dataChanged.connect(self._view.update)


class ParameterWidget(QWidget):
    """Public widget exposing the original ParameterWidget interface."""

    parameters_changed = Signal(dict)

    def __init__(
        self, parent: QWidget | None = None, df: pd.DataFrame | None = None
    ) -> None:
        super().__init__(parent)

        self._model = ParameterModel(df)
        self._view = ParameterView(self)
        self._controller = ParameterController(self._view, self._model)

        layout = QVBoxLayout(self)
        layout.addWidget(self._view)


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    df = pd.DataFrame(
        {
            "value": [1.0, 2.0, 3.0],
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 10.0, 10.0],
        },
    )
    widget = ParameterWidget(df=df)
    widget.show()
    sys.exit(app.exec())
