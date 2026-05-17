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
