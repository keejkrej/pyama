"""Reusable Qt host for the `view` web canvas."""

import json
import os
from pathlib import Path

import pyama_gui._qtwebengine_bootstrap  # noqa: F401
from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget


def resolve_view_canvas_url() -> QUrl:
    """Resolve the preferred frontend bundle for the embedded Align canvas."""

    env_url = os.getenv("PYAMA_ALIGN_CANVAS_URL") or os.getenv("VIEW_PYSIDE6_URL")
    if env_url:
        return QUrl(env_url)

    dist_index = (
        Path(__file__).resolve().parents[5]
        / "view"
        / "apps"
        / "view-py"
        / "web"
        / "dist"
        / "index.html"
    )
    if dist_index.exists():
        return QUrl.fromLocalFile(str(dist_index.resolve()))

    return QUrl("data:text/html,<html><body></body></html>")


class _CanvasBridge(QObject):
    def __init__(self, owner: "ViewCanvas") -> None:
        super().__init__()
        self._owner = owner

    @Slot(str)
    def postMessage(self, message: str) -> None:
        self._owner.message_received.emit(message)


class ViewCanvas(QWebEngineView):
    """QWebEngineView wrapper for the shared `view` canvas frontend."""

    message_received = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        settings = self.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
            True,
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
            True,
        )
        self._web_channel = QWebChannel(self.page())
        self._bridge = _CanvasBridge(self)
        self._web_channel.registerObject("viewBridge", self._bridge)
        self.page().setWebChannel(self._web_channel)
        self.setMinimumSize(320, 240)
        self.setUrl(resolve_view_canvas_url())

    def publish_state(self, payload: dict[str, object]) -> None:
        self.page().runJavaScript(
            f"window.__viewPyApplyState?.({json.dumps(payload)});"
        )
