"""
ND2 file loading utilities for microscopy data.
"""

from dataclasses import dataclass
import numpy as np
from pathlib import Path
import nd2
import xarray as xr


@dataclass
class ND2Metadata:
    nd2_path: Path
    basename: str
    height: int
    width: int
    n_frames: int
    n_fovs: int
    n_channels: int
    timepoints: list[float]
    channels: list[str]
    dtype: str


def load_nd2(nd2_path: Path) -> tuple[xr.DataArray, ND2Metadata]:
    """Load an ND2 file and return the xarray view and extracted metadata.

    Returns a tuple of (xarray.DataArray, ND2Metadata).
    Timepoints are returned in microseconds when available; otherwise a best-effort
    numeric list is provided.
    """
    basename = nd2_path.name.replace(".nd2", "")
    try:
        da = nd2.imread(str(nd2_path), xarray=True, dask=True)

        sizes = getattr(da, "sizes", {})
        height = int(sizes.get("Y", 0))
        width = int(sizes.get("X", 0))
        n_frames = int(sizes.get("T", 1))
        n_fovs = int(sizes.get("P", 1))
        n_channels = int(sizes.get("C", 1))

        # Channels from coordinates if present; otherwise placeholder names
        ch_coord = da.coords.get("C") if hasattr(da, "coords") else None
        if ch_coord is not None:
            try:
                channels = [str(v) for v in ch_coord.values.tolist()]
            except Exception:
                channels = [str(v) for v in np.asarray(ch_coord.values).tolist()]
        else:
            channels = [f"C{i}" for i in range(n_channels)]

        # Timepoints: treat T coord as numeric; fallback to sequential indices
        timepoints: list[float] = []
        t_coord = da.coords.get("T") if hasattr(da, "coords") else None
        if t_coord is not None:
            t_values = np.asarray(t_coord.values)
            try:
                timepoints = t_values.astype(float).tolist()
            except Exception:
                timepoints = [float(i) for i in range(n_frames)]
        else:
            timepoints = [float(i) for i in range(n_frames)]

        metadata: ND2Metadata = ND2Metadata(
            nd2_path=nd2_path,
            basename=basename,
            height=height,
            width=width,
            n_frames=n_frames,
            n_fovs=n_fovs,
            n_channels=n_channels,
            timepoints=timepoints,
            channels=channels,
            dtype=str(da.dtype),
        )
        return da, metadata
    except Exception as e:
        raise RuntimeError(f"Failed to load ND2: {str(e)}")


def get_nd2_frame(da: xr.DataArray, f: int, c: int, t: int) -> np.ndarray:
    """Return a frame or slice from an ND2 xarray DataArray.

    Args:
        da: ND2 xarray DataArray.
        f: FOV index, or -1 for all.
        c: Channel index, or -1 for all.
        t: Time index, or -1 for all.

    Returns:
        np.ndarray: The selected frame(s) as a numpy array.
    """
    indexers = {}
    if "P" in da.dims and f != -1:
        indexers["P"] = f
    if "C" in da.dims and c != -1:
        indexers["C"] = c
    if "T" in da.dims and t != -1:
        indexers["T"] = t
    return da.isel(**indexers).compute().values
