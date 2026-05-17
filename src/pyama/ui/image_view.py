"""pyqtgraph image viewer with rectangular overlays."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from pyama.contrast import ContrastLimits, percentile_limits
from pyama.grid import GridCell

GridHitTest = Callable[[float, float], int | None]


class OverlayDragViewBox(pg.ViewBox):
    overlayDragged = QtCore.Signal(float, float)

    def mouseDragEvent(self, event, axis=None) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            event.accept()
            if not event.isStart() and not event.isFinish():
                current = self.mapToView(event.pos())
                previous = self.mapToView(event.lastPos())
                self.overlayDragged.emit(
                    current.x() - previous.x(),
                    current.y() - previous.y(),
                )
            return
        super().mouseDragEvent(event, axis=axis)


class ImageCanvas(pg.PlotWidget):
    cellClicked = QtCore.Signal(int)
    overlayDragged = QtCore.Signal(float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        self.view_box = OverlayDragViewBox()
        super().__init__(parent=parent, viewBox=self.view_box)
        self.setAspectLocked(True)
        self.hideAxis("left")
        self.hideAxis("bottom")
        self.image = pg.ImageItem()
        self.mask = pg.ImageItem()
        self.addItem(self.image)
        self.addItem(self.mask)
        self._rects: list[QtWidgets.QGraphicsRectItem] = []
        self._hit_test: GridHitTest | None = None
        self._frame: np.ndarray | None = None
        self._contrast_limits: ContrastLimits | None = None
        self._grid_visible = True
        self._grid_opacity = 0.3
        self._last_grid: tuple[list[GridCell], set[int], GridHitTest | None] = ([], set(), None)
        self.view_box.overlayDragged.connect(self.overlayDragged.emit)
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = np.asarray(frame)
        self._contrast_limits = percentile_limits(self._frame)
        self._render_frame()
        self.mask.setRect(self.image.boundingRect())
        self.setRange(xRange=(0, frame.shape[1]), yRange=(0, frame.shape[0]), padding=0.02)

    def set_contrast_limits(self, low: float, high: float) -> None:
        if high <= low:
            high = low + 1.0
        self._contrast_limits = ContrastLimits(low=float(low), high=float(high))
        self._render_frame()

    def auto_contrast(self) -> ContrastLimits | None:
        if self._frame is None:
            return None
        self._contrast_limits = percentile_limits(self._frame)
        self._render_frame()
        return self._contrast_limits

    def contrast_limits(self) -> ContrastLimits | None:
        return self._contrast_limits

    def set_grid_visible(self, visible: bool) -> None:
        self._grid_visible = visible
        self.set_grid(*self._last_grid)

    def set_grid_opacity(self, opacity: float) -> None:
        self._grid_opacity = min(1.0, max(0.0, opacity))
        self.set_grid(*self._last_grid)

    def _render_frame(self) -> None:
        if self._frame is None:
            return
        limits = self._contrast_limits or percentile_limits(self._frame)
        self.image.setImage(
            self._frame.T,
            levels=(limits.low, limits.high),
            autoLevels=False,
        )

    def set_mask(self, mask: np.ndarray | None) -> None:
        if mask is None:
            self.mask.clear()
            return
        rgba = np.zeros((*mask.shape, 4), dtype=np.uint8)
        rgba[..., 0] = 255
        rgba[..., 3] = (np.asarray(mask) > 0).astype(np.uint8) * 110
        self.mask.setImage(rgba.transpose(1, 0, 2), autoLevels=False)

    def set_grid(
        self,
        cells: list[GridCell],
        excluded: set[int],
        hit_test: GridHitTest | None,
    ) -> None:
        self._last_grid = (list(cells), set(excluded), hit_test)
        self.clear_grid()
        if not self._grid_visible:
            self._hit_test = None
            return
        self._hit_test = hit_test
        for cell in cells:
            color = QtGui.QColor("#ffcc00" if cell.index not in excluded else "#d62728")
            color.setAlphaF(self._grid_opacity)
            pen = pg.mkPen(color, width=2)
            rect = QtWidgets.QGraphicsRectItem(
                cell.bbox.x, cell.bbox.y, cell.bbox.width, cell.bbox.height
            )
            rect.setPen(pen)
            rect.setBrush(QtGui.QBrush(QtCore.Qt.BrushStyle.NoBrush))
            self.addItem(rect)
            self._rects.append(rect)

    def clear_grid(self) -> None:
        for rect in self._rects:
            self.removeItem(rect)
        self._rects.clear()

    def _on_mouse_clicked(self, event) -> None:
        if self._hit_test is None:
            return
        point = self.plotItem.vb.mapSceneToView(event.scenePos())
        cell = self._hit_test(point.x(), point.y())
        if cell is not None:
            self.cellClicked.emit(cell)
