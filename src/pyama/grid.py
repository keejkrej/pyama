"""Grid enumeration and exclusion logic for ROI alignment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, cos, floor, isfinite, pi, radians, sin
from typing import Literal

GridKind = Literal["rect", "hex"]


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class GridSpec:
    kind: GridKind = "rect"
    offset_x: float = 0.0
    offset_y: float = 0.0
    vector_a: float = 80.0
    vector_b: float = 80.0
    pattern_width: int = 64
    pattern_height: int = 64
    rotation_degrees: float = 0.0
    rows: int | None = None
    cols: int | None = None
    origin_x: float | None = None
    origin_y: float | None = None
    roi_width: int | None = None
    roi_height: int | None = None
    spacing_x: float | None = None
    spacing_y: float | None = None
    hex_offset: float | None = None

    def __post_init__(self) -> None:
        if self.origin_x is not None:
            object.__setattr__(self, "offset_x", float(self.origin_x))
        if self.origin_y is not None:
            object.__setattr__(self, "offset_y", float(self.origin_y))
        if self.roi_width is not None:
            object.__setattr__(self, "pattern_width", int(self.roi_width))
        if self.roi_height is not None:
            object.__setattr__(self, "pattern_height", int(self.roi_height))
        if self.spacing_x is not None:
            object.__setattr__(self, "vector_a", float(self.spacing_x))
        if self.spacing_y is not None:
            object.__setattr__(self, "vector_b", float(self.spacing_y))
        object.__setattr__(self, "origin_x", self.offset_x)
        object.__setattr__(self, "origin_y", self.offset_y)
        object.__setattr__(self, "roi_width", self.pattern_width)
        object.__setattr__(self, "roi_height", self.pattern_height)
        object.__setattr__(self, "spacing_x", self.vector_a)
        object.__setattr__(self, "spacing_y", self.vector_b)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if data["rows"] is None:
            data.pop("rows")
        if data["cols"] is None:
            data.pop("cols")
        for alias in (
            "origin_x",
            "origin_y",
            "roi_width",
            "roi_height",
            "spacing_x",
            "spacing_y",
            "hex_offset",
        ):
            data.pop(alias, None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> GridSpec:
        normalized = dict(data)
        aliases = {
            "shape": "kind",
            "origin_x": "offset_x",
            "origin_y": "offset_y",
            "roi_width": "pattern_width",
            "roi_height": "pattern_height",
            "spacing_x": "vector_a",
            "spacing_y": "vector_b",
            "tx": "offset_x",
            "ty": "offset_y",
            "spacingA": "vector_a",
            "spacingB": "vector_b",
            "cellWidth": "pattern_width",
            "cellHeight": "pattern_height",
        }
        for old_key, new_key in aliases.items():
            if old_key in normalized and new_key not in normalized:
                normalized[new_key] = normalized[old_key]
        if "rotation" in normalized and "rotation_degrees" not in normalized:
            normalized["rotation_degrees"] = float(normalized["rotation"]) * 180.0 / pi

        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in normalized.items() if key in allowed})


@dataclass(frozen=True)
class GridCell:
    index: int
    row: int
    col: int
    bbox: BBox
    raw_bbox: BBox | None = None


def enumerate_grid(
    spec: GridSpec, image_width: int | None = None, image_height: int | None = None
) -> list[GridCell]:
    if spec.rows is not None and spec.cols is not None:
        return _enumerate_finite_grid(spec)
    if image_width is not None and image_height is not None:
        return _enumerate_visible_grid(spec, image_width, image_height)
    return []


def _enumerate_finite_grid(spec: GridSpec) -> list[GridCell]:
    cells: list[GridCell] = []
    for row in range(max(spec.rows, 0)):
        row_offset = spec.vector_a * 0.5 if spec.kind == "hex" and row % 2 else 0.0
        for col in range(max(spec.cols, 0)):
            x = round(spec.offset_x + col * spec.vector_a + row_offset)
            y = round(spec.offset_y + row * spec.vector_b)
            bbox = BBox(int(x), int(y), int(spec.pattern_width), int(spec.pattern_height))
            cells.append(
                GridCell(
                    index=len(cells),
                    row=row,
                    col=col,
                    bbox=bbox,
                    raw_bbox=bbox,
                )
            )
    return cells


def _enumerate_visible_grid(spec: GridSpec, image_width: int, image_height: int) -> list[GridCell]:
    image_width = max(0, int(image_width))
    image_height = max(0, int(image_height))
    if image_width == 0 or image_height == 0:
        return []

    pattern_width = max(1, int(round(spec.pattern_width)))
    pattern_height = max(1, int(round(spec.pattern_height)))
    vector_a = max(1.0, float(spec.vector_a))
    vector_b = max(1.0, float(spec.vector_b))
    rotation = radians(float(spec.rotation_degrees))
    second_angle = rotation + (pi / 2 if spec.kind == "rect" else pi / 3)
    basis_a = (cos(rotation) * vector_a, sin(rotation) * vector_a)
    basis_b = (cos(second_angle) * vector_b, sin(second_angle) * vector_b)
    origin_x = image_width / 2 + float(spec.offset_x)
    origin_y = image_height / 2 + float(spec.offset_y)
    half_width = pattern_width / 2
    half_height = pattern_height / 2
    determinant = basis_a[0] * basis_b[1] - basis_a[1] * basis_b[0]

    if abs(determinant) <= 1e-6:
        min_vector = max(1.0, min(vector_a, vector_b))
        grid_range = ceil(max(image_width, image_height) / min_vector) + 3
        i_min = j_min = -grid_range
        i_max = j_max = grid_range
    else:
        corners = (
            (-half_width, -half_height),
            (image_width + half_width, -half_height),
            (-half_width, image_height + half_height),
            (image_width + half_width, image_height + half_height),
        )
        i_values: list[float] = []
        j_values: list[float] = []
        for corner_x, corner_y in corners:
            dx = corner_x - origin_x
            dy = corner_y - origin_y
            i = (dx * basis_b[1] - dy * basis_b[0]) / determinant
            j = (dy * basis_a[0] - dx * basis_a[1]) / determinant
            if isfinite(i) and isfinite(j):
                i_values.append(i)
                j_values.append(j)

        if not i_values or not j_values:
            return []
        i_min = floor(min(i_values) - 1e-6)
        i_max = ceil(max(i_values) + 1e-6)
        j_min = floor(min(j_values) - 1e-6)
        j_max = ceil(max(j_values) + 1e-6)

    cells: list[GridCell] = []
    for i in range(i_min, i_max + 1):
        for j in range(j_min, j_max + 1):
            center_x = origin_x + i * basis_a[0] + j * basis_b[0]
            center_y = origin_y + i * basis_a[1] + j * basis_b[1]
            raw_x = round(center_x - half_width)
            raw_y = round(center_y - half_height)
            raw_bbox = BBox(raw_x, raw_y, pattern_width, pattern_height)
            clipped_x = min(max(raw_x, 0), image_width)
            clipped_y = min(max(raw_y, 0), image_height)
            clipped_x2 = min(max(raw_x + pattern_width, 0), image_width)
            clipped_y2 = min(max(raw_y + pattern_height, 0), image_height)
            width = clipped_x2 - clipped_x
            height = clipped_y2 - clipped_y
            if width <= 0 or height <= 0:
                continue
            cells.append(
                GridCell(
                    index=len(cells),
                    row=i,
                    col=j,
                    bbox=BBox(clipped_x, clipped_y, width, height),
                    raw_bbox=raw_bbox,
                )
            )
    return cells


def auto_excluded_cells(spec: GridSpec, image_width: int, image_height: int) -> set[int]:
    excluded: set[int] = set()
    for cell in enumerate_grid(spec, image_width, image_height):
        box = cell.raw_bbox or cell.bbox
        if box.x < 0 or box.y < 0 or box.x2 > image_width or box.y2 > image_height:
            excluded.add(cell.index)
    return excluded


def cell_at(
    spec: GridSpec,
    x: float,
    y: float,
    image_width: int | None = None,
    image_height: int | None = None,
) -> int | None:
    for cell in enumerate_grid(spec, image_width, image_height):
        box = cell.bbox
        if box.x <= x < box.x2 and box.y <= y < box.y2:
            return cell.index
    return None
