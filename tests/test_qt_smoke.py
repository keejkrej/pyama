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


def test_aligner_canvas_drag_defaults_and_save_controls() -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from pyama.aligner import AlignerWindow
    from pyama.ui.qt import get_app

    app = get_app()
    aligner = AlignerWindow()

    assert aligner.opacity_slider.value() == 30
    assert aligner.canvas._grid_opacity == pytest.approx(0.3)
    assert aligner.save_btn.text() == "Save"
    assert aligner.crop_btn.text() == "Crop"
    assert not any(
        button.text() in {"Batch Crop", "Cancel Crop"}
        for button in aligner.findChildren(aligner.save_btn.__class__)
    )

    aligner.move_overlay(2.5, -1.5)
    assert aligner.offset_x.value() == pytest.approx(2.5)
    assert aligner.offset_y.value() == pytest.approx(-1.5)

    aligner.close()
    app.processEvents()


def test_aligner_drag_respects_selected_tool() -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from pyama.aligner import AlignerWindow
    from pyama.ui.qt import get_app

    app = get_app()
    aligner = AlignerWindow()

    aligner.set_active_tool("rotate")
    aligner.apply_tool_drag(5, 3)
    assert aligner.rotation.value() == pytest.approx(5)
    assert aligner.offset_x.value() == pytest.approx(0)
    assert aligner.offset_y.value() == pytest.approx(0)

    aligner.set_active_tool("zoom_vector")
    aligner.apply_tool_drag(7, 9)
    assert aligner.vector_a.value() == pytest.approx(87)
    assert aligner.vector_b.value() == pytest.approx(89)
    assert aligner.offset_x.value() == pytest.approx(0)
    assert aligner.offset_y.value() == pytest.approx(0)

    aligner.set_active_tool("zoom_pattern")
    aligner.apply_tool_drag(4.2, 5.8)
    assert aligner.pattern_w.value() == 68
    assert aligner.pattern_h.value() == 70
    assert aligner.offset_x.value() == pytest.approx(0)
    assert aligner.offset_y.value() == pytest.approx(0)

    aligner.set_active_tool("pan")
    aligner.apply_tool_drag(2, -3)
    assert aligner.offset_x.value() == pytest.approx(2)
    assert aligner.offset_y.value() == pytest.approx(-3)

    aligner.close()
    app.processEvents()


def test_aligner_parameter_inputs_commit_on_enter() -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    from PySide6 import QtWidgets

    from pyama.aligner import AlignerWindow
    from pyama.ui.qt import get_app

    app = get_app()
    aligner = AlignerWindow()

    for spin in aligner.findChildren(QtWidgets.QAbstractSpinBox):
        assert not spin.keyboardTracking()

    aligner.close()
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
            def __init__(self, calls=calls) -> None:
                calls.append("window")

        def get_app(calls=calls) -> object:
            calls.append("app")
            return object()

        def run_window(window: object, calls=calls) -> int:
            calls.append("run")
            return 0

        monkeypatch.setattr(module, "get_app", get_app)
        monkeypatch.setattr(module, window_name, Window)
        monkeypatch.setattr(module, "run_window", run_window)

        assert module.main() == 0
        assert calls == ["app", "window", "run"]
