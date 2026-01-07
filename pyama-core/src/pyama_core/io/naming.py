"""
File naming conventions for pyama processing outputs.

This module centralizes all file naming patterns used across the processing
pipeline. Services should use these functions instead of hardcoding paths.

Naming pattern: {base_name}_fov_{fov:03d}_{type}[_ch_{channel}].{ext}

    Types:
    - pc: Phase contrast stack (.npy)
    - fl: Fluorescence stack (.npy)
    - seg_labeled: Labeled (untracked) segmentation mask (.npy)
    - seg_tracked: Tracked cell labels (.npy)
    - fl_background: Background interpolation (.npy)
    - crops: Cropped cell data (.h5)
    - traces: Extracted traces (.csv)

"""

from pathlib import Path


def fov_dir(output_dir: Path, fov: int) -> Path:
    """Get FOV directory path.

    Args:
        output_dir: Base output directory
        fov: FOV index

    Returns:
        Path to FOV directory: {output_dir}/fov_{fov:03d}
    """
    return output_dir / f"fov_{fov:03d}"


def pc_stack(output_dir: Path, base_name: str, fov: int, channel: int) -> Path:
    """Get phase contrast stack path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index
        channel: Channel index

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_pc_ch_{channel}.npy
    """
    return fov_dir(output_dir, fov) / f"{base_name}_fov_{fov:03d}_pc_ch_{channel}.npy"


def fl_stack(output_dir: Path, base_name: str, fov: int, channel: int) -> Path:
    """Get fluorescence stack path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index
        channel: Channel index

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_fl_ch_{channel}.npy
    """
    return fov_dir(output_dir, fov) / f"{base_name}_fov_{fov:03d}_fl_ch_{channel}.npy"


def seg_labeled(output_dir: Path, base_name: str, fov: int, channel: int) -> Path:
    """Get labeled (untracked) segmentation path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index
        channel: Channel index (typically PC channel)

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_seg_labeled_ch_{channel}.npy
    """
    return (
        fov_dir(output_dir, fov)
        / f"{base_name}_fov_{fov:03d}_seg_labeled_ch_{channel}.npy"
    )


def seg_tracked(output_dir: Path, base_name: str, fov: int, channel: int) -> Path:
    """Get tracked cell labels path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index
        channel: Channel index (typically PC channel)

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_seg_tracked_ch_{channel}.npy
    """
    return (
        fov_dir(output_dir, fov)
        / f"{base_name}_fov_{fov:03d}_seg_tracked_ch_{channel}.npy"
    )


def fl_background(output_dir: Path, base_name: str, fov: int, channel: int) -> Path:
    """Get fluorescence background estimation path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index
        channel: Fluorescence channel index

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_fl_background_ch_{channel}.npy
    """
    return (
        fov_dir(output_dir, fov)
        / f"{base_name}_fov_{fov:03d}_fl_background_ch_{channel}.npy"
    )


def crops_h5(output_dir: Path, base_name: str, fov: int) -> Path:
    """Get cropped cell data HDF5 path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_crops.h5
    """
    return fov_dir(output_dir, fov) / f"{base_name}_fov_{fov:03d}_crops.h5"


def traces_csv(output_dir: Path, base_name: str, fov: int) -> Path:
    """Get traces CSV path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name
        fov: FOV index

    Returns:
        Path: {fov_dir}/{base_name}_fov_{fov:03d}_traces.csv
    """
    return fov_dir(output_dir, fov) / f"{base_name}_fov_{fov:03d}_traces.csv"


def merged_traces_csv(output_dir: Path, base_name: str) -> Path:
    """Get merged traces CSV path.

    Args:
        output_dir: Base output directory
        base_name: Dataset base name

    Returns:
        Path: {output_dir}/{base_name}_traces_merged.csv
    """
    return output_dir / f"{base_name}_traces_merged.csv"


# Discovery functions - find existing files


def discover_fovs(output_dir: Path) -> list[int]:
    """Discover FOV indices from existing fov_* directories.

    Args:
        output_dir: Base output directory

    Returns:
        Sorted list of FOV indices found
    """
    fovs = []
    for d in output_dir.iterdir():
        if d.is_dir() and d.name.startswith("fov_"):
            try:
                fov = int(d.name[4:])
                fovs.append(fov)
            except ValueError:
                continue
    return sorted(fovs)


def discover_traces(output_dir: Path) -> list[Path]:
    """Discover all traces CSV files in output directory.

    Args:
        output_dir: Base output directory

    Returns:
        List of paths to traces CSV files found
    """
    traces = []
    for fov in discover_fovs(output_dir):
        fov_path = fov_dir(output_dir, fov)
        for f in fov_path.glob("*_traces.csv"):
            traces.append(f)
    return sorted(traces)


def discover_seg_tracked(output_dir: Path, fov: int) -> Path | None:
    """Discover tracked segmentation file for a FOV.

    Args:
        output_dir: Base output directory
        fov: FOV index

    Returns:
        Path to seg_tracked file if found, None otherwise
    """
    fov_path = fov_dir(output_dir, fov)
    if not fov_path.exists():
        return None
    matches = list(fov_path.glob("*_seg_tracked_ch_*.npy"))
    return matches[0] if matches else None


def discover_crops(output_dir: Path, fov: int) -> Path | None:
    """Discover crops H5 file for a FOV.

    Args:
        output_dir: Base output directory
        fov: FOV index

    Returns:
        Path to crops H5 file if found, None otherwise
    """
    fov_path = fov_dir(output_dir, fov)
    if not fov_path.exists():
        return None
    matches = list(fov_path.glob("*_crops.h5"))
    return matches[0] if matches else None


__all__ = [
    "fov_dir",
    "pc_stack",
    "fl_stack",
    "seg_labeled",
    "seg_tracked",
    "fl_background",
    "crops_h5",
    "traces_csv",
    "merged_traces_csv",
    "discover_fovs",
    "discover_traces",
    "discover_seg_tracked",
    "discover_crops",
]
