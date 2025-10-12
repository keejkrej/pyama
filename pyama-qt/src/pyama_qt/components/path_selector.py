"""Minimal PathSelector widget.

Features kept intentionally small:
- Label, QLineEdit, Browse button
- Normalized string path stored in `path` property (never None)
- QLineEdit updated when `path` is set programmatically
- Simple browse behavior for files or directories
- `path_changed` signal emitted with normalized string when path changes
"""

from enum import Enum
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal, Property
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class PathType(Enum):
    FILE = "file"
    DIRECTORY = "directory"


class PathSelector(QWidget):
    """A compact widget for selecting a file or directory."""

    path_changed = Signal()

    def __init__(
        self,
        label: str = "",
        path_type: PathType = PathType.FILE,
        dialog_title: str = "",
        file_filter: str = "All Files (*)",
        default_dir: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._path_type = path_type
        self._dialog_title = dialog_title or (
            f"Select {label}" if label else "Select Path"
        )
        self._file_filter = file_filter
        self._default_dir = str(Path(default_dir).expanduser()) if default_dir else ""
        # Internal path is always a string (empty when unset)
        self._path: str = ""

        self._build_ui(label)
        self._connect_signals()

    def _build_ui(self, label: str) -> None:
        layout = QHBoxLayout(self)
        if label:
            layout.addWidget(QLabel(label))

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Enter path or click Browse")
        layout.addWidget(self._path_edit)

        self._browse_btn = QPushButton("Browse")
        layout.addWidget(self._browse_btn)

    def _connect_signals(self) -> None:
        self._browse_btn.clicked.connect(self._on_browse)
        self._path_edit.textChanged.connect(self._on_edit)

    @Property(str, notify=path_changed)
    def path(self) -> str:
        """Current path as a string (empty string if unset)."""
        return self._path

    @path.setter
    def path(self, value: Optional[str]) -> None:
        """Set the path. Accepts Path-like or string or None/empty to clear."""
        new = self._normalize(value)
        if new == self._path:
            return

        self._path = new
        # Update QLineEdit without causing the textChanged handler to re-fire
        if self._path_edit.text() != new:
            self._path_edit.blockSignals(True)
            self._path_edit.setText(new)
            self._path_edit.blockSignals(False)

        self.path_changed.emit()

    def _normalize(self, value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            # expand user but do not require existence
            return str(Path(value).expanduser())
        except Exception:
            # Fallback to raw string if Path conversion fails
            return str(value)

    def _on_browse(self) -> None:
        start_dir = self._default_dir or self._path or str(Path.home())
        if self._path_type == PathType.FILE:
            chosen, _ = QFileDialog.getOpenFileName(
                self, self._dialog_title, start_dir, self._file_filter
            )
            path = chosen
        else:
            path = QFileDialog.getExistingDirectory(self, self._dialog_title, start_dir)

        if path:
            self.path = path

    def _on_edit(self, text: str) -> None:
        # Update property from user edit; setter will handle deduplication
        self.path = text or ""
