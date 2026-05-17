"""Qt worker helpers."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from PySide6 import QtCore, QtWidgets

from pyama.progress import CancelToken, ProgressEvent


class WorkerThread(QtCore.QThread):
    progress = QtCore.Signal(object)
    failed = QtCore.Signal(str)
    succeeded = QtCore.Signal(object)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.cancel = CancelToken()

    def run(self) -> None:
        def on_progress(event: ProgressEvent) -> None:
            self.progress.emit(event)

        try:
            result = self._fn(
                *self._args,
                **self._kwargs,
                on_progress=on_progress,
                cancel=self.cancel,
            )
        except Exception as exc:  # pragma: no cover - exercised in UI
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


def get_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def run_window(window: QtWidgets.QWidget) -> int:
    app = get_app()
    window.show()
    return app.exec()
