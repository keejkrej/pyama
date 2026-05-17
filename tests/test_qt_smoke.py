from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_qt_windows_construct() -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from pyama.aligner import AlignerWindow
    from pyama.annotator import AnnotatorWindow
    from pyama.ui.qt import get_app

    app = get_app()
    aligner = AlignerWindow()
    annotator = AnnotatorWindow()
    assert aligner.windowTitle() == "Pyama Aligner"
    assert annotator.windowTitle() == "Pyama Annotator"
    aligner.close()
    annotator.close()
    app.processEvents()


def test_entry_points_create_app_before_window(monkeypatch: pytest.MonkeyPatch) -> None:
    import pyama.aligner as aligner
    import pyama.annotator as annotator

    for module, window_name in (
        (aligner, "AlignerWindow"),
        (annotator, "AnnotatorWindow"),
    ):
        calls: list[str] = []

        class Window:
            def __init__(self) -> None:
                calls.append("window")

        def get_app() -> object:
            calls.append("app")
            return object()

        def run_window(window: object) -> int:
            calls.append("run")
            return 0

        monkeypatch.setattr(module, "get_app", get_app)
        monkeypatch.setattr(module, window_name, Window)
        monkeypatch.setattr(module, "run_window", run_window)

        assert module.main() == 0
        assert calls == ["app", "window", "run"]
