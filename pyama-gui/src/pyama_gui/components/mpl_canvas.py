"""Shared and componentized Matplotlib canvas widget for embedding plots in Qt."""

import matplotlib
import numpy as np
from matplotlib.patches import Circle, Polygon

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QStackedLayout, QWidget


class _CanvasPlaceholder(QWidget):
    """Flat theme-matched placeholder used when no plot content exists."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        painter.end()
        super().paintEvent(event)


class MplCanvas(QWidget):
    """Widget that swaps between a Qt placeholder and a Matplotlib canvas."""

    artist_picked = Signal(str)
    artist_right_clicked = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        width: int = 5,
        height: int = 3,
        dpi: int = 100,
    ):
        super().__init__(parent)
        self._fig = Figure(figsize=(width, height), dpi=dpi, constrained_layout=True)
        self._axes = self._fig.add_subplot(111)
        self._canvas = FigureCanvas(self._fig)
        self._placeholder = _CanvasPlaceholder(self)
        self._has_content = False
        self._image_artist = None
        self._overlay_artists: dict[str, object] = {}

        self._build_ui()
        self._fig.canvas.mpl_connect("pick_event", self._on_pick)
        self._set_content_visible(False)

    def _build_ui(self) -> None:
        layout = QStackedLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._placeholder)
        layout.addWidget(self._canvas)
        self._stack = layout

    @property
    def figure(self) -> Figure:
        return self._fig

    @Slot()
    def _on_pick(self, event):
        if hasattr(event.artist, "get_label"):
            label = event.artist.get_label()
            if label and not label.startswith("_"):
                if hasattr(event.mouseevent, "button") and event.mouseevent.button == 3:
                    self.artist_right_clicked.emit(label)
                else:
                    self.artist_picked.emit(label)

    def _set_content_visible(self, visible: bool) -> None:
        self._has_content = visible
        self._stack.setCurrentWidget(self._canvas if visible else self._placeholder)

    def _prepare_plot_axes(
        self,
        *,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        show_grid: bool = False,
    ) -> None:
        self._axes.cla()
        if title:
            self._axes.set_title(title)
        self._axes.set_xlabel(x_label)
        self._axes.set_ylabel(y_label)
        if show_grid:
            self._axes.grid(True, linestyle=":", linewidth=0.5)

    def draw_idle(self) -> None:
        if self._has_content:
            self._canvas.draw_idle()

    def clear(self, clear_figure: bool = False) -> None:
        self._axes.cla()
        self._image_artist = None
        self._overlay_artists = {}
        if clear_figure:
            self._fig.clear()
            self._axes = self._fig.add_subplot(111)
        self._set_content_visible(False)
        self._placeholder.update()

    def plot_image(
        self,
        image_data: np.ndarray,
        cmap: str = "gray",
        vmin: float = 0,
        vmax: float = 255,
    ) -> None:
        if self._image_artist is None:
            self._axes.cla()
            self._axes.set_xticks([])
            self._axes.set_yticks([])
            self._axes.set_aspect("equal")
            self._image_artist = self._axes.imshow(
                image_data,
                cmap=cmap,
                vmin=vmin,
                vmax=vmax,
                origin="upper",
                interpolation="nearest",
                zorder=1,
                extent=[0, image_data.shape[1], image_data.shape[0], 0],
            )
        else:
            self._image_artist.set_data(image_data)
            self._image_artist.set_clim(vmin, vmax)
            self._image_artist.set_extent(
                [0, image_data.shape[1], image_data.shape[0], 0]
            )

        self._canvas.draw()
        self._set_content_visible(True)

    def update_image(
        self,
        image_data: np.ndarray,
        vmin: float | None = None,
        vmax: float | None = None,
    ) -> None:
        if self._image_artist:
            self._image_artist.set_data(image_data)
            if vmin is not None and vmax is not None:
                self._image_artist.set_clim(vmin, vmax)
            self._image_artist.set_extent(
                [0, image_data.shape[1], image_data.shape[0], 0]
            )
            self._canvas.draw()
            self._set_content_visible(True)

    def plot_lines(
        self,
        lines_data: list,
        styles_data: list,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
    ) -> None:
        self._prepare_plot_axes(
            title=title,
            x_label=x_label,
            y_label=y_label,
            show_grid=True,
        )

        for i, (x_data, y_data) in enumerate(lines_data):
            style = styles_data[i] if i < len(styles_data) else {}
            plot_style = style.get("plot_style", "line")

            if plot_style == "line":
                self._axes.plot(
                    x_data,
                    y_data,
                    color=style.get("color", "blue"),
                    linewidth=style.get("linewidth", 1.0),
                    alpha=style.get("alpha", 1.0),
                    label=style.get("label"),
                    picker=True,
                    pickradius=5,
                )
            elif plot_style == "scatter":
                self._axes.scatter(
                    x_data,
                    y_data,
                    s=style.get("s", 20),
                    color=style.get("color", "blue"),
                    alpha=style.get("alpha", 0.6),
                    label=style.get("label"),
                )

        if any(style.get("label") for style in styles_data):
            self._axes.legend(loc="upper left")

        self._canvas.draw()
        self._set_content_visible(True)

    def plot_histogram(
        self, data: np.ndarray, bins: int, x_label: str, y_label: str, title: str = ""
    ) -> None:
        self._prepare_plot_axes(
            title=title,
            x_label=x_label,
            y_label=y_label,
            show_grid=True,
        )
        self._axes.hist(data, bins=bins, alpha=0.75)
        self._canvas.draw()
        self._set_content_visible(True)

    def plot_boxplot(
        self,
        groups: dict[str, list[float]],
        *,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
    ) -> None:
        self._prepare_plot_axes(
            title=title,
            x_label=x_label,
            y_label=y_label,
            show_grid=False,
        )
        self._axes.grid(True, axis="y", linestyle=":", linewidth=0.5)

        labels = []
        data = []
        for label, values in groups.items():
            clean_values = [value for value in values if np.isfinite(value)]
            if not clean_values:
                continue
            labels.append(label)
            data.append(clean_values)

        if data:
            self._axes.boxplot(
                data,
                labels=labels,
                patch_artist=True,
                showfliers=False,
            )
            self._axes.tick_params(axis="x", rotation=20)

        self._canvas.draw()
        self._set_content_visible(True)

    def plot_overlay(self, overlay_id: str, properties: dict) -> None:
        if overlay_id in self._overlay_artists:
            self.remove_overlay(overlay_id)

        shape_type = properties.get("type", "circle")
        if shape_type == "circle":
            artist = Circle(
                properties.get("xy", (0, 0)),
                radius=properties.get("radius", 10),
                edgecolor=properties.get("edgecolor", "red"),
                facecolor=properties.get("facecolor", "none"),
                linewidth=properties.get("linewidth", 2.0),
                zorder=properties.get("zorder", 5),
                label=overlay_id,
                picker=True,
            )
            self._axes.add_patch(artist)
            self._overlay_artists[overlay_id] = artist
        elif shape_type == "polygon":
            artist = Polygon(
                properties.get("xy"),
                edgecolor=properties.get("edgecolor", "red"),
                facecolor=properties.get("facecolor", "none"),
                linewidth=properties.get("linewidth", 1.0),
                zorder=properties.get("zorder", 5),
                label=overlay_id,
                picker=True,
            )
            self._axes.add_patch(artist)
            self._overlay_artists[overlay_id] = artist

        self._canvas.draw()
        self._set_content_visible(True)

    def update_overlay(self, overlay_id: str, properties: dict) -> None:
        if overlay_id not in self._overlay_artists:
            return

        artist = self._overlay_artists[overlay_id]
        if isinstance(artist, Circle):
            if "xy" in properties:
                artist.set_center(properties["xy"])
            if "radius" in properties:
                artist.set_radius(properties["radius"])
        self._canvas.draw_idle()

    def remove_overlay(self, overlay_id: str) -> None:
        if overlay_id not in self._overlay_artists:
            return

        artist = self._overlay_artists[overlay_id]
        try:
            if hasattr(artist, "remove"):
                artist.remove()
            else:
                if artist in self._axes.patches:
                    self._axes.patches.remove(artist)
                if artist in self._axes.artists:
                    self._axes.artists.remove(artist)
        except (ValueError, KeyError, NotImplementedError, AttributeError):
            pass

        del self._overlay_artists[overlay_id]
        self._canvas.draw_idle()

    def clear_overlays(self) -> None:
        for overlay_id in list(self._overlay_artists.keys()):
            self.remove_overlay(overlay_id)
