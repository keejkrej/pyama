"""ND2 reader adapter, ported from the local convert project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .base import ImageInfo, ReaderSession, ensure_2d


@dataclass(frozen=True)
class FrameLookup:
    sequence_axes: tuple[str, ...]
    index_by_coords: dict[tuple[int, ...], int]


class ND2ReaderAdapter:
    name = "nd2"
    suffixes = (".nd2",)

    def supports(self, input_path: Path) -> bool:
        return input_path.suffix.lower() in self.suffixes

    def inspect(self, input_path: Path) -> ImageInfo:
        import nd2

        handle = nd2.ND2File(str(input_path))
        try:
            sizes = handle.sizes
            return ImageInfo(
                n_pos=sizes.get("P", 1),
                n_time=sizes.get("T", 1),
                n_chan=sizes.get("C", 1),
                n_z=sizes.get("Z", 1),
                size_y=sizes.get("Y"),
                size_x=sizes.get("X"),
            )
        finally:
            handle.close()

    def open(self, input_path: Path) -> ReaderSession:
        import nd2

        handle = nd2.ND2File(str(input_path))
        sizes = handle.sizes
        info = ImageInfo(
            n_pos=sizes.get("P", 1),
            n_time=sizes.get("T", 1),
            n_chan=sizes.get("C", 1),
            n_z=sizes.get("Z", 1),
            size_y=sizes.get("Y"),
            size_x=sizes.get("X"),
        )
        lookup = self.build_frame_lookup(handle)

        def read_frame(p: int, t: int, c: int, z: int) -> np.ndarray:
            return self.read_frame_2d(handle, lookup, p, t, c, z)

        return ReaderSession(info=info, read_frame=read_frame, close=handle.close)

    @staticmethod
    def build_frame_lookup(handle) -> FrameLookup:
        from nd2._util import loop_indices

        experiment = handle.experiment() if callable(handle.experiment) else handle.experiment
        loop_entries = tuple(loop_indices(experiment))
        if not loop_entries:
            return FrameLookup(sequence_axes=(), index_by_coords={(): 0})

        sequence_axes = tuple(
            axis for axis in ("P", "T", "C", "Z") if any(axis in entry for entry in loop_entries)
        )
        index_by_coords = {
            tuple(entry.get(axis, 0) for axis in sequence_axes): seq_index
            for seq_index, entry in enumerate(loop_entries)
        }
        return FrameLookup(sequence_axes=sequence_axes, index_by_coords=index_by_coords)

    @staticmethod
    def read_frame_2d(handle, lookup: FrameLookup, p: int, t: int, c: int, z: int) -> np.ndarray:
        coords = {"P": p, "T": t, "C": c, "Z": z}
        seq_key = tuple(coords[axis] for axis in lookup.sequence_axes)
        if seq_key not in lookup.index_by_coords:
            raise ValueError(f"No ND2 frame found for coordinates P={p}, T={t}, C={c}, Z={z}")

        frame = np.asarray(handle.read_frame(lookup.index_by_coords[seq_key]))
        if "C" not in lookup.sequence_axes and handle.sizes.get("C", 1) > 1:
            if frame.ndim >= 3 and frame.shape[0] == handle.sizes["C"]:
                frame = frame[c]
            elif frame.ndim >= 3 and frame.shape[-1] == handle.sizes["C"]:
                frame = frame[..., c]
            else:
                raise ValueError("Unable to locate in-pixel channel axis in ND2 frame data")
        return ensure_2d(frame)
