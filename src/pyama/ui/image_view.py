"""pyqtgraph image viewer with rectangular overlays."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from pyama.contrast import percentile_limits
from pyama.grid import GridCell


class ImageCanvas(pg.PlotWidget):
    cellClicked = QtCore.Signal(int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setAspectLocked(True)
        self.hideAxis("left")
        self.hideAxis("bottom")
        self.image = pg.ImageItem()
        self.mask = pg.ImageItem()
        self.addItem(self.image)
        self.addItem(self.mask)
        self._rects: list[QtWidgets.QGraphicsRectItem] = []
        self._hit_test: Callable[[float, float], int | None] | None = None
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

    def set_frame(self, frame: np.ndarray) -> None:
        limits = percentile_limits(frame)
        self.image.setImage(np.asarray(frame).T, levels=(limits.low, limits.high), autoLevels=False)
        self.mask.setRect(self.image.boundingRect())
        self.setRange(xRange=(0, frame.shape[1]), yRange=(0, frame.shape[0]), padding=0.02)

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
        hit_test: Callable[[float, float], int | None] | None,
    ) -> None:
        self.clear_grid()
        self._hit_test = hit_test
        for cell in cells:
            pen = pg.mkPen("#ffcc00" if cell.index not in excluded else "#d62728", width=2)
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
