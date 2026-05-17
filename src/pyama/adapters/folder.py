"""Folder and TIFF stack source readers."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from .base import ImageInfo, ReaderSession, ensure_2d

IMAGE_SUFFIXES = (".tif", ".tiff", ".png", ".jpg", ".jpeg")
FRAME_RE = re.compile(
    r"(?:channel|c)(?P<c>\d+).*?(?:position|pos|p)(?P<p>\d+).*?(?:time|t)(?P<t>\d+).*?(?:z)(?P<z>\d+)",
    re.IGNORECASE,
)
POS_RE = re.compile(r"^Pos(?P<p>\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedFrame:
    path: Path
    p: int
    t: int
    c: int
    z: int


def _read_image(path: Path) -> np.ndarray:
    if path.suffix.lower() in (".tif", ".tiff"):
        import tifffile

        return ensure_2d(tifffile.imread(str(path)))
    with Image.open(path) as img:
        frame = np.asarray(img)
    if frame.ndim == 3 and frame.shape[-1] in (3, 4):
        frame = frame[..., :3].mean(axis=-1).astype(frame.dtype)
    return ensure_2d(frame)


def parse_frame_path(path: Path) -> ParsedFrame | None:
    match = FRAME_RE.search(path.name)
    if match:
        return ParsedFrame(
            path=path,
            p=int(match.group("p")),
            t=int(match.group("t")),
            c=int(match.group("c")),
            z=int(match.group("z")),
        )

    pos_match = POS_RE.match(path.parent.name)
    if pos_match:
        digits = [int(part) for part in re.findall(r"\d+", path.stem)]
        if len(digits) >= 3:
            return ParsedFrame(
                path=path,
                p=int(pos_match.group("p")),
                c=digits[0],
                t=digits[1],
                z=digits[2],
            )
    return None


def scan_image_folder(input_path: Path) -> dict[tuple[int, int, int, int], Path]:
    root = input_path
    files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
    frames: dict[tuple[int, int, int, int], Path] = {}
    fallback_by_pos: dict[int, list[Path]] = defaultdict(list)
    for path in files:
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        parsed = parse_frame_path(path)
        if parsed is None:
            pos_match = POS_RE.match(path.parent.name)
            fallback_by_pos[int(pos_match.group("p")) if pos_match else 0].append(path)
            continue
        frames[(parsed.p, parsed.t, parsed.c, parsed.z)] = path

    if frames:
        return frames

    for p, paths in fallback_by_pos.items():
        for t, path in enumerate(sorted(paths)):
            frames[(p, t, 0, 0)] = path
    return frames


def _info_from_frames(frames: dict[tuple[int, int, int, int], Path]) -> ImageInfo:
    if not frames:
        raise ValueError("No supported image files found")
    keys = list(frames)
    sample = _read_image(frames[keys[0]])
    return ImageInfo(
        n_pos=max(k[0] for k in keys) + 1,
        n_time=max(k[1] for k in keys) + 1,
        n_chan=max(k[2] for k in keys) + 1,
        n_z=max(k[3] for k in keys) + 1,
        size_y=int(sample.shape[-2]),
        size_x=int(sample.shape[-1]),
    )


class ImageFolderReaderAdapter:
    name = "image-folder"
    suffixes = IMAGE_SUFFIXES

    def supports(self, input_path: Path) -> bool:
        return input_path.is_dir() or input_path.suffix.lower() in self.suffixes

    def inspect(self, input_path: Path) -> ImageInfo:
        return _info_from_frames(scan_image_folder(input_path))

    def open(self, input_path: Path) -> ReaderSession:
        frames = scan_image_folder(input_path)
        info = _info_from_frames(frames)

        def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
            key = (p, t, c, z)
            if key not in frames:
                raise ValueError(f"No image frame found for P={p}, T={t}, C={c}, Z={z}")
            return _read_image(frames[key])

        return ReaderSession(info=info, read_frame=read_frame, close=lambda: None)
