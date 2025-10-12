"""Reusable path selector widget for files and directories."""

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PathType(Enum):
    """Type of path selection."""

    FILE = "file"
    DIRECTORY = "directory"


class PathSelector(QWidget):
    """A reusable widget for selecting files or directories.

    Provides a label, line edit field for displaying/editing the path,
    and a browse button to open a file/directory dialog.

    Signals:
        path_changed: Emitted when the path is changed (either via browse or manual edit)
    """

    path_changed = Signal(str)  # Emits the new path as a string

    def __init__(
        self,
        label: str,
        path_type: PathType = PathType.FILE,
        dialog_title: str = "",
        file_filter: str = "All Files (*)",
        default_dir: str = "",
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the path selector.

        Args:
            label: Label text to display
            path_type: Whether to select files or directories
            dialog_title: Title for the file dialog
            file_filter: File filter for file dialogs (e.g., "YAML Files (*.yaml *.yml)")
            default_dir: Default directory to open in dialog
            parent: Parent widget
        """
        super().__init__(parent)
        self._path_type = path_type
        self._dialog_title = dialog_title or (
            f"Select {label}" if label else "Select Path"
        )
        self._file_filter = file_filter
        self._default_dir = default_dir

        self._build_ui(label)
        self._connect_signals()

    def _build_ui(self, label: str) -> None:
        """Build the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top row: label and browse button
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel(label))
        top_row.addStretch()

        self._browse_btn = QPushButton("Browse")
        top_row.addWidget(self._browse_btn)

        layout.addLayout(top_row)

        # Bottom row: line edit for path
        self._path_edit = QLineEdit()
        layout.addWidget(self._path_edit)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._browse_btn.clicked.connect(self._on_browse_clicked)
        self._path_edit.textChanged.connect(self.path_changed.emit)

    def _on_browse_clicked(self) -> None:
        """Handle browse button click."""
        if self._path_type == PathType.FILE:
            path, _ = QFileDialog.getOpenFileName(
                self,
                self._dialog_title,
                self._default_dir or self._path_edit.text(),
                self._file_filter,
                options=QFileDialog.Option.DontUseNativeDialog,
            )
        else:  # PathType.DIRECTORY
            path = QFileDialog.getExistingDirectory(
                self,
                self._dialog_title,
                self._default_dir or self._path_edit.text(),
                options=QFileDialog.Option.DontUseNativeDialog,
            )

        if path:
            self.set_path(path)

    # ---------------------------- Public API -------------------------------- #

    def set_path(self, path: Path | str) -> None:
        """Set the displayed path.

        Args:
            path: Path to display
        """
        self._path_edit.setText(str(path))

    def get_path(self) -> str:
        """Get the current path as a string.

        Returns:
            Current path text
        """
        return self._path_edit.text().strip()

    def get_path_obj(self) -> Path:
        """Get the current path as a Path object.

        Returns:
            Current path as Path object (expanded)
        """
        return Path(self.get_path()).expanduser()

    def clear(self) -> None:
        """Clear the path field."""
        self._path_edit.clear()

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the widget.

        Args:
            enabled: Whether to enable the widget
        """
        self._path_edit.setEnabled(enabled)
        self._browse_btn.setEnabled(enabled)
