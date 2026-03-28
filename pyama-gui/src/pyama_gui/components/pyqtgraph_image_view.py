"""Pyqtgraph-based image viewer for visualization workflows."""

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QGraphicsPathItem, QStackedLayout, QWidget

from pyama_gui.types.common import OverlaySpec


class _CanvasPlaceholder(QWidget):
    """Flat theme-matched placeholder used when no image content exists."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.end()
        super().paintEvent(event)


class _ClickablePathItem(QGraphicsPathItem):
    """Graphics item that forwards left and right clicks by overlay id."""

    def __init__(
        self,
        overlay_id: str,
        *,
        on_left_click,
        on_right_click,
    ) -> None:
        super().__init__()
        self._overlay_id = overlay_id
        self._on_left_click = on_left_click
        self._on_right_click = on_right_click
        self.setAcceptedMouseButtons(
            Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_left_click(self._overlay_id)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._on_right_click(self._overlay_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def shape(self) -> QPainterPath:
        stroker = QPainterPathStroker()
        stroker.setWidth(max(8.0, self.pen().widthF() + 6.0))
        return stroker.createStroke(self.path())


class PyQtGraphImageView(QWidget):
    """Qt image viewer backed by pyqtgraph with clickable contour overlays."""

    overlay_clicked = Signal(str)
    overlay_right_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._has_content = False
        self._image_shape: tuple[int, int] | None = None
        self._overlay_items: dict[str, _ClickablePathItem] = {}

        self._plot_widget = pg.PlotWidget(self)
        self._plot_widget.setMenuEnabled(False)
        self._plot_widget.hideAxis("left")
        self._plot_widget.hideAxis("bottom")
        self._plot_widget.setAspectLocked(True)
        self._view_box = self._plot_widget.getViewBox()
        self._view_box.invertY(True)
        self._view_box.setMenuEnabled(False)
        self._image_item = pg.ImageItem(axisOrder="row-major")
        self._plot_widget.addItem(self._image_item)
        self._placeholder = _CanvasPlaceholder(self)

        self._build_ui()
        self._set_content_visible(False)

    def _build_ui(self) -> None:
        layout = QStackedLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._placeholder)
        layout.addWidget(self._plot_widget)
        self._stack = layout

    def _set_content_visible(self, visible: bool) -> None:
        self._has_content = visible
        self._stack.setCurrentWidget(
            self._plot_widget if visible else self._placeholder
        )

    def clear(self) -> None:
        self.clear_overlays()
        self._image_item.clear()
        self._image_shape = None
        self._set_content_visible(False)
        self._placeholder.update()

    def set_image(
        self,
        image: np.ndarray,
        *,
        levels: tuple[float, float] | None = None,
    ) -> None:
        image_data = np.asarray(image)
        if image_data.ndim != 2:
            raise ValueError("PyQtGraphImageView expects a 2D image.")

        preserve_view = self._has_content and self._image_shape == image_data.shape
        x_range, y_range = self._view_box.viewRange()
        self._image_item.setImage(image_data, autoLevels=False)
        self._image_item.setRect(
            QRectF(0.0, 0.0, float(image_data.shape[1]), float(image_data.shape[0]))
        )

        if levels is None:
            min_value = float(np.min(image_data))
            max_value = float(np.max(image_data))
            if min_value == max_value:
                max_value = min_value + 1.0
        else:
            min_value = float(levels[0])
            max_value = float(levels[1])
            if min_value == max_value:
                max_value = min_value + 1.0
        self._image_item.setLevels((min_value, max_value))
        self._image_shape = image_data.shape
        self._set_content_visible(True)

        if preserve_view:
            self._view_box.setXRange(*x_range, padding=0.0)
            self._view_box.setYRange(*y_range, padding=0.0)
        else:
            self._view_box.autoRange(padding=0.0)

    def set_overlays(self, overlays: list[OverlaySpec]) -> None:
        self.clear_overlays()
        for overlay in overlays:
            item = self._build_overlay_item(overlay)
            if item is None:
                continue
            self._view_box.addItem(item)
            self._overlay_items[overlay.overlay_id] = item

    def clear_overlays(self) -> None:
        for overlay_id, item in list(self._overlay_items.items()):
            self._view_box.removeItem(item)
            del self._overlay_items[overlay_id]

    @staticmethod
    def _as_float(value: object, default: float) -> float:
        if isinstance(value, int | float):
            return float(value)
        return default

    def _build_overlay_item(self, overlay: OverlaySpec) -> _ClickablePathItem | None:
        properties = overlay.properties
        shape_type = str(properties.get("type", "polygon"))
        if shape_type not in {"polygon", "path"}:
            return None

        xy = np.asarray(properties.get("xy", []), dtype=float)
        if xy.ndim != 2 or xy.shape[0] < 2 or xy.shape[1] != 2:
            return None

        path = QPainterPath()
        path.moveTo(float(xy[0, 0]), float(xy[0, 1]))
        for x_coord, y_coord in xy[1:]:
            path.lineTo(float(x_coord), float(y_coord))
        if shape_type == "polygon":
            path.closeSubpath()

        item = _ClickablePathItem(
            overlay.overlay_id,
            on_left_click=self.overlay_clicked.emit,
            on_right_click=self.overlay_right_clicked.emit,
        )
        item.setPath(path)
        item.setPen(
            pg.mkPen(
                color=properties.get("edgecolor", "red"),
                width=self._as_float(properties.get("linewidth", 2.0), 2.0),
            )
        )
        facecolor = properties.get("facecolor")
        item.setBrush(
            pg.mkBrush(facecolor) if facecolor is not None else pg.mkBrush(None)
        )
        item.setOpacity(self._as_float(properties.get("alpha", 1.0), 1.0))
        item.setZValue(self._as_float(properties.get("zorder", 10), 10.0))
        return item
