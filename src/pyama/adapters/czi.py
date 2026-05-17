"""CZI reader adapter, ported from the local convert project."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import numpy as np

from .base import ImageInfo, ReaderSession, ensure_2d


class CZIReaderAdapter:
    name = "czi"
    suffixes = (".czi",)

    def supports(self, input_path: Path) -> bool:
        return input_path.suffix.lower() in self.suffixes

    @staticmethod
    def axis_size(ranges: Mapping[str, tuple[int, int]], axis: str) -> int:
        start, stop = ranges.get(axis, (0, 1))
        if start < 0 or stop < start:
            raise ValueError(f"Invalid bounding range for axis {axis}: {(start, stop)!r}")
        return stop - start

    def inspect(self, input_path: Path) -> ImageInfo:
        from pylibCZIrw import czi as pyczi

        with pyczi.open_czi(str(input_path)) as handle:
            box = dict(handle.total_bounding_box)
            scenes = dict(handle.scenes_bounding_rectangle)
            return ImageInfo(
                n_pos=len(scenes) if scenes else 1,
                n_time=self.axis_size(box, "T"),
                n_chan=self.axis_size(box, "C"),
                n_z=self.axis_size(box, "Z"),
                size_y=self.axis_size(box, "Y"),
                size_x=self.axis_size(box, "X"),
            )

    def open(self, input_path: Path) -> ReaderSession:
        from pylibCZIrw import czi as pyczi

        context = pyczi.open_czi(str(input_path))
        handle = context.__enter__()
        box = dict(handle.total_bounding_box)
        scenes = dict(handle.scenes_bounding_rectangle)
        scene_ids = tuple(scenes) if scenes else ()
        n_chan = self.axis_size(box, "C")
        info = ImageInfo(
            n_pos=len(scene_ids) if scene_ids else 1,
            n_time=self.axis_size(box, "T"),
            n_chan=n_chan,
            n_z=self.axis_size(box, "Z"),
            size_y=self.axis_size(box, "Y"),
            size_x=self.axis_size(box, "X"),
        )

        def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
            plane = {"T": t, "Z": z}
            if n_chan > 1:
                plane["C"] = c
            kwargs: dict[str, object] = {"plane": plane}
            if scene_ids:
                kwargs["scene"] = scene_ids[p]
            return ensure_2d(np.asarray(handle.read(**kwargs)))

        def close() -> None:
            context.__exit__(None, None, None)

        return ReaderSession(info=info, read_frame=read_frame, close=close)
