from csv import DictReader
from pathlib import Path

import numpy as np

_BBOX_COLUMNS = ["crop", "x", "y", "w", "h"]


def bbox_csv_path(*, output_dir: Path, position_id: int) -> Path:
    return output_dir / "bbox" / f"Pos{int(position_id)}.csv"


def load_bbox_rows(
    *,
    output_dir: Path,
    position_id: int,
    frame_width: int,
    frame_height: int,
) -> tuple[np.ndarray, np.ndarray]:
    path = bbox_csv_path(output_dir=output_dir, position_id=position_id)
    if not path.exists():
        raise FileNotFoundError(f"Missing bbox CSV for position {position_id}: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = DictReader(handle)
        if reader.fieldnames != _BBOX_COLUMNS:
            raise ValueError(
                f"Invalid bbox CSV header for position {position_id}: "
                f"expected {_BBOX_COLUMNS}, got {reader.fieldnames}"
            )

        rows: list[tuple[int, int, int, int, int]] = []
        seen_crop_ids: set[int] = set()
        for line_number, row in enumerate(reader, start=2):
            if row is None:
                continue
            try:
                crop = int(str(row["crop"]).strip())
                x = int(str(row["x"]).strip())
                y = int(str(row["y"]).strip())
                w = int(str(row["w"]).strip())
                h = int(str(row["h"]).strip())
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid bbox CSV row {line_number} for position {position_id}: {row}"
                ) from exc

            if crop < 0:
                raise ValueError(
                    f"Invalid crop id at row {line_number} in {path}: crop must be >= 0"
                )
            if crop in seen_crop_ids:
                raise ValueError(f"Duplicate crop id {crop} in {path}")
            if x < 0 or y < 0:
                raise ValueError(
                    f"Invalid bbox at row {line_number} in {path}: x and y must be >= 0"
                )
            if w <= 0 or h <= 0:
                raise ValueError(
                    f"Invalid bbox at row {line_number} in {path}: w and h must be > 0"
                )
            if x + w > int(frame_width) or y + h > int(frame_height):
                raise ValueError(
                    f"Invalid bbox at row {line_number} in {path}: "
                    f"bbox exceeds frame bounds {frame_width}x{frame_height}"
                )

            seen_crop_ids.add(crop)
            rows.append((crop, x, y, w, h))

    rows.sort(key=lambda item: item[0])
    if not rows:
        return np.zeros((0,), dtype=np.int32), np.zeros((0, 4), dtype=np.int32)

    roi_ids = np.asarray([row[0] for row in rows], dtype=np.int32)
    bbox_rows = np.asarray([row[1:] for row in rows], dtype=np.int32)
    return roi_ids, bbox_rows


__all__ = [
    "bbox_csv_path",
    "load_bbox_rows",
]
