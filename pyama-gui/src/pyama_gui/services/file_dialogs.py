"""File dialog service abstractions for MVVM-friendly path selection."""

from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QFileDialog


class FileDialogService(Protocol):
    """Abstract file dialog operations used by view-models."""

    def select_directory(self, caption: str, directory: str) -> Path | None:
        """Prompt the user to choose a directory."""

    def select_open_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        """Prompt the user to choose an existing file."""

    def select_save_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        """Prompt the user to choose an output file."""


class QtFileDialogService:
    """Qt-backed file dialog service implementation."""

    def select_directory(self, caption: str, directory: str) -> Path | None:
        path = QFileDialog.getExistingDirectory(
            None,
            caption,
            directory,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return Path(path) if path else None

    def select_open_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        path, _ = QFileDialog.getOpenFileName(
            None,
            caption,
            directory,
            file_filter,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return Path(path) if path else None

    def select_save_file(
        self, caption: str, directory: str, file_filter: str
    ) -> Path | None:
        path, _ = QFileDialog.getSaveFileName(
            None,
            caption,
            directory,
            file_filter,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        return Path(path) if path else None
