"""Frame extraction from microscopy files (functional API).

This module extracts frames from ND2 files and writes them to memory-mapped
NPY arrays. The public entrypoint ``copy_frames`` handles a single channel
for a single FOV.
"""

import numpy as np
from numpy.lib.format import open_memmap
from pathlib import Path
from typing import Callable

from pyama_core.io import get_microscopy_frame


def copy_frames(
    img,
    fov: int,
    channel: int,
    n_frames: int,
    output_path: Path,
    height: int,
    width: int,
    progress_callback: Callable | None = None,
    cancel_event=None,
) -> bool:
    """Copy frames from a microscopy file to a memory-mapped NPY array.

    Extracts all frames for a single channel of a single FOV and writes
    them to a memory-mapped NPY file.

    Args:
        img: Loaded microscopy file object (from load_microscopy_file).
        fov: Field of view index.
        channel: Channel index to extract.
        n_frames: Number of frames to extract.
        output_path: Path for the output NPY file.
        height: Frame height in pixels.
        width: Frame width in pixels.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.

    Returns:
        True if copying completed successfully, False if cancelled.

    Raises:
        Exception: If file operations fail.
    """
    memmap = None
    try:
        memmap = open_memmap(
            output_path,
            mode="w+",
            dtype=np.uint16,
            shape=(n_frames, height, width),
        )

        for t in range(n_frames):
            if cancel_event and cancel_event.is_set():
                # Clean up partial file on cancellation
                try:
                    del memmap
                    memmap = None
                    output_path.unlink(missing_ok=True)
                except Exception:
                    pass
                return False

            memmap[t] = get_microscopy_frame(img, fov, channel, t)

            if progress_callback is not None:
                progress_callback(t, n_frames, "Copying")

        memmap.flush()
        return True

    except Exception:
        if memmap is not None:
            try:
                del memmap
            except Exception:
                pass
        raise
    finally:
        if memmap is not None:
            try:
                del memmap
            except Exception:
                pass
