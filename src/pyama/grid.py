"""Grid enumeration and exclusion logic for ROI alignment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
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
    origin_x: float = 0.0
    origin_y: float = 0.0
    roi_width: int = 64
    roi_height: int = 64
    spacing_x: float = 80.0
    spacing_y: float = 80.0
    rows: int = 4
    cols: int = 4
    hex_offset: float = 0.5

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> GridSpec:
        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(frozen=True)
class GridCell:
    index: int
    row: int
    col: int
    bbox: BBox


def enumerate_grid(spec: GridSpec) -> list[GridCell]:
    cells: list[GridCell] = []
    for row in range(max(spec.rows, 0)):
        row_offset = spec.spacing_x * spec.hex_offset if spec.kind == "hex" and row % 2 else 0.0
        for col in range(max(spec.cols, 0)):
            x = round(spec.origin_x + col * spec.spacing_x + row_offset)
            y = round(spec.origin_y + row * spec.spacing_y)
            cells.append(
                GridCell(
                    index=len(cells),
                    row=row,
                    col=col,
                    bbox=BBox(int(x), int(y), int(spec.roi_width), int(spec.roi_height)),
                )
            )
    return cells


def auto_excluded_cells(spec: GridSpec, image_width: int, image_height: int) -> set[int]:
    excluded: set[int] = set()
    for cell in enumerate_grid(spec):
        box = cell.bbox
        if box.x < 0 or box.y < 0 or box.x2 > image_width or box.y2 > image_height:
            excluded.add(cell.index)
    return excluded


def cell_at(spec: GridSpec, x: float, y: float) -> int | None:
    for cell in enumerate_grid(spec):
        box = cell.bbox
        if box.x <= x < box.x2 and box.y <= y < box.y2:
            return cell.index
    return None
