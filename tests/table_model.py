from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtWidgets import QApplication, QTableView, QVBoxLayout, QWidget
import pandas as pd
import sys


class PandasModel(QAbstractTableModel):
    def __init__(self, df):
        super().__init__()
        self._df = df

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.DisplayRole:
            value = self._df.iloc[index.row(), index.column()]
            # Handle different data types
            return str(value)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            else:
                return str(self._df.index[section])
        return None

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole and index.isValid():
            # Convert value to appropriate type based on column dtype
            try:
                self._df.iloc[index.row(), index.column()] = value
                self.dataChanged.emit(index, index, [role])
                return True
            except Exception as e:
                print(f"Error setting data: {e}")
                return False
        return False

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandas DataFrame with QTableView")
        self.resize(600, 400)

        # Create a DataFrame
        df = pd.DataFrame(
            {
                "Name": ["Alice", "Bob", "Charlie", "Diana"],
                "Age": [25, 30, 35, 28],
                "Role": ["Engineer", "Designer", "Manager", "Developer"],
                "Salary": [75000, 68000, 95000, 72000],
            }
        )

        # Create model and view
        self.model = PandasModel(df)
        self.table_view = QTableView()
        self.table_view.setModel(self.model)

        # Optional: Adjust appearance
        self.table_view.resizeColumnsToContents()

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.table_view)
        self.setLayout(layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
