"""Lisca-compatible workspace persistence and ROI generation."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .adapters.base import ReaderSession
from .grid import BBox, GridCell, GridSpec, enumerate_grid
from .progress import CancelToken, ProgressCallback, ProgressEvent


@dataclass(frozen=True)
class Alignment:
    pos: int
    source: str
    grid: GridSpec
    excluded: set[int]


@dataclass(frozen=True)
class RoiRecord:
    pos: int
    roi: int
    path: str
    bbox: BBox
    row: int
    col: int
    shape: tuple[int, ...]


@dataclass(frozen=True)
class RoiWorkspace:
    root: Path
    records: list[RoiRecord]


def _json_default(value: Any) -> Any:
    if isinstance(value, set):
        return sorted(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer | np.floating):
        return value.item()
    return value


def save_bbox(root: Path, pos: int, bbox: BBox) -> Path:
    path = root / "bbox" / f"Pos{pos}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["x", "y", "width", "height"])
        writer.writeheader()
        writer.writerow(asdict(bbox))
    return path


def load_bbox(root: Path, pos: int) -> BBox | None:
    path = root / "bbox" / f"Pos{pos}.csv"
    if not path.exists():
        return None
    with path.open("r", newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    return BBox(
        x=int(row["x"]),
        y=int(row["y"]),
        width=int(row["width"]),
        height=int(row["height"]),
    )


def save_alignment(root: Path, alignment: Alignment) -> Path:
    path = root / "align" / f"Pos{alignment.pos}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pos": alignment.pos,
        "source": alignment.source,
        "grid": alignment.grid,
        "excluded": alignment.excluded,
    }
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")
    return path


def load_alignment(root: Path, pos: int) -> Alignment | None:
    path = root / "align" / f"Pos{pos}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Alignment(
        pos=int(payload.get("pos", pos)),
        source=str(payload.get("source", "")),
        grid=GridSpec.from_dict(payload.get("grid", {})),
        excluded=set(int(item) for item in payload.get("excluded", [])),
    )


def crop_frame(frame: np.ndarray, bbox: BBox) -> np.ndarray:
    return np.asarray(frame)[bbox.y : bbox.y2, bbox.x : bbox.x2]


def write_roi_tiff(path: Path, stack: np.ndarray) -> None:
    import tifffile

    if path.exists():
        path.unlink()
    tifffile.imwrite(str(path), stack, metadata={"axes": "TCZYX"})


def crop_rois(
    session: ReaderSession,
    output_root: Path,
    *,
    source: str,
    pos: int,
    grid: GridSpec,
    excluded: Iterable[int] = (),
    on_progress: ProgressCallback | None = None,
    cancel: CancelToken | None = None,
) -> list[RoiRecord]:
    excluded_set = set(excluded)
    cells = [cell for cell in enumerate_grid(grid) if cell.index not in excluded_set]
    total = len(cells) * session.info.n_time * session.info.n_chan * session.info.n_z
    out_dir = output_root / "roi" / f"Pos{pos}"
    out_dir.mkdir(parents=True, exist_ok=True)
    records: list[RoiRecord] = []
    done = 0

    for roi_index, cell in enumerate(cells):
        _raise_if_cancelled(cancel)
        stack = np.empty(
            (
                session.info.n_time,
                session.info.n_chan,
                session.info.n_z,
                cell.bbox.height,
                cell.bbox.width,
            ),
            dtype=np.asarray(session.read_frame(pos, 0, 0, 0)).dtype,
        )
        for t in range(session.info.n_time):
            for c in range(session.info.n_chan):
                for z in range(session.info.n_z):
                    _raise_if_cancelled(cancel)
                    stack[t, c, z] = crop_frame(session.read_frame(pos, t, c, z), cell.bbox)
                    done += 1
                    _emit(on_progress, "crop", done, total, f"Cropping Pos{pos} Roi{roi_index}")

        path = out_dir / f"Roi{roi_index}.tif"
        write_roi_tiff(path, stack)
        records.append(
            RoiRecord(
                pos=pos,
                roi=roi_index,
                path=path.name,
                bbox=cell.bbox,
                row=cell.row,
                col=cell.col,
                shape=tuple(int(dim) for dim in stack.shape),
            )
        )

    write_roi_index(output_root, pos, source, grid, excluded_set, records)
    _emit(on_progress, "finish", done, total, f"Wrote {len(records)} ROIs")
    return records


def write_roi_index(
    root: Path,
    pos: int,
    source: str,
    grid: GridSpec,
    excluded: set[int],
    records: list[RoiRecord],
) -> Path:
    path = root / "roi" / f"Pos{pos}" / "index.json"
    payload = {
        "pos": pos,
        "source": source,
        "grid": grid,
        "excluded": excluded,
        "rois": records,
    }
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")
    return path


def scan_roi_workspace(root: Path) -> RoiWorkspace:
    records: list[RoiRecord] = []
    for index_path in sorted((root / "roi").glob("Pos*/index.json")):
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        pos = int(payload.get("pos", index_path.parent.name[3:]))
        for item in payload.get("rois", []):
            bbox_data = item["bbox"]
            records.append(
                RoiRecord(
                    pos=pos,
                    roi=int(item["roi"]),
                    path=str(index_path.parent / item["path"]),
                    bbox=BBox(**{k: int(bbox_data[k]) for k in ("x", "y", "width", "height")}),
                    row=int(item.get("row", 0)),
                    col=int(item.get("col", 0)),
                    shape=tuple(int(dim) for dim in item.get("shape", ())),
                )
            )
    return RoiWorkspace(root=root, records=records)


def cell_bbox_union(cells: Iterable[GridCell]) -> BBox:
    boxes = [cell.bbox for cell in cells]
    if not boxes:
        return BBox(0, 0, 0, 0)
    x1 = min(box.x for box in boxes)
    y1 = min(box.y for box in boxes)
    x2 = max(box.x2 for box in boxes)
    y2 = max(box.y2 for box in boxes)
    return BBox(x1, y1, x2 - x1, y2 - y1)


def _emit(
    callback: ProgressCallback | None, phase: str, done: int, total: int, message: str
) -> None:
    if callback is not None:
        callback(ProgressEvent(phase=phase, done=done, total=total, message=message))


def _raise_if_cancelled(cancel: CancelToken | None) -> None:
    if cancel is not None:
        cancel.raise_if_cancelled()
