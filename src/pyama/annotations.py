"""Label and ROI annotation persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Label:
    id: str
    name: str
    color: str = "#ffcc00"


@dataclass(frozen=True)
class Annotation:
    pos: int
    roi: int
    channel: int
    time: int
    z: int
    label_id: str | None
    mask_path: str | None


DEFAULT_LABELS = [
    Label(id="unassigned", name="Unassigned", color="#808080"),
    Label(id="positive", name="Positive", color="#2ca02c"),
    Label(id="negative", name="Negative", color="#d62728"),
]


def load_labels(root: Path) -> list[Label]:
    path = root / "annotations" / "labels.json"
    if not path.exists():
        return list(DEFAULT_LABELS)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Label(**item) for item in payload.get("labels", payload)]


def save_labels(root: Path, labels: list[Label]) -> Path:
    path = root / "annotations" / "labels.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"labels": [asdict(label) for label in labels]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def annotation_dir(root: Path, pos: int, roi: int) -> Path:
    return root / "annotations" / "roi" / f"Pos{pos}" / f"Roi{roi}"


def annotation_stem(channel: int, time: int, z: int) -> str:
    return f"C{channel}_T{time}_Z{z}"


def save_annotation(
    root: Path,
    *,
    pos: int,
    roi: int,
    channel: int,
    time: int,
    z: int,
    label_id: str | None,
    mask: np.ndarray | None,
) -> Annotation:
    out_dir = annotation_dir(root, pos, roi)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = annotation_stem(channel, time, z)
    mask_path: str | None = None
    if mask is not None:
        png = out_dir / f"{stem}.png"
        Image.fromarray((np.asarray(mask) > 0).astype(np.uint8) * 255).save(png)
        mask_path = png.name

    annotation = Annotation(
        pos=pos,
        roi=roi,
        channel=channel,
        time=time,
        z=z,
        label_id=label_id,
        mask_path=mask_path,
    )
    (out_dir / f"{stem}.json").write_text(
        json.dumps(asdict(annotation), indent=2) + "\n",
        encoding="utf-8",
    )
    return annotation


def load_annotation(
    root: Path, *, pos: int, roi: int, channel: int, time: int, z: int
) -> tuple[Annotation | None, np.ndarray | None]:
    out_dir = annotation_dir(root, pos, roi)
    stem = annotation_stem(channel, time, z)
    json_path = out_dir / f"{stem}.json"
    if not json_path.exists():
        return None, None
    annotation = Annotation(**json.loads(json_path.read_text(encoding="utf-8")))
    mask = None
    if annotation.mask_path:
        png = out_dir / annotation.mask_path
        if png.exists():
            with Image.open(png) as img:
                mask = np.asarray(img) > 0
    return annotation, mask
