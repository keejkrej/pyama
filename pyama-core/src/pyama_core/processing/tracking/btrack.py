"""Bayesian tracking (btrack) for actively moving cells.

This module uses BayesianTracker for tracking cells that move more actively.
btrack uses probabilistic models and Kalman filtering to handle complex motion
patterns, making it suitable for cells with rapid movement, occlusions, and
non-linear trajectories.

The public entrypoint is ``track_cell`` which operates in-place on the
preallocated output array.

KNOWN ISSUES:
- btrack 0.7.0 crashes with Eigen assertion when configure({}) is called with
  an empty dict. This is fixed by using the default cell config file when available.
- If crashes occur, use IoU tracking instead (set tracking_method: iou in config)
"""

import numpy as np
from typing import Callable
import logging
import sys
import types

logger = logging.getLogger(__name__)

# Patch cvxopt.glpk if not available (only needed for optimization, not basic tracking)
# This allows btrack to import even if cvxopt wasn't built with GLPK support
if 'cvxopt.glpk' not in sys.modules:
    try:
        import cvxopt.glpk
    except (ImportError, ModuleNotFoundError):
        # Create fake module - optimization won't work but tracking will
        cvxopt_glpk = types.ModuleType('cvxopt.glpk')
        cvxopt_glpk.ilp = lambda *args, **kwargs: None
        sys.modules['cvxopt.glpk'] = cvxopt_glpk

# Try to import btrack, raise informative error if not available
BTRACK_AVAILABLE = False
BayesianTracker = None
segmentation_to_objects = None
update_segmentation = None
constants = None
btrack = None

try:
    from btrack import BayesianTracker
    from btrack.io import segmentation_to_objects
    from btrack.utils import update_segmentation
    from btrack import constants
    import btrack
    
    # Try to import datasets to get default config file
    # This avoids the btrack 0.7.0 crash when using configure({}) with empty dict
    DEFAULT_CONFIG_FILE = None
    try:
        from btrack import datasets
        if hasattr(datasets, 'cell_config'):
            DEFAULT_CONFIG_FILE = datasets.cell_config()
    except (ImportError, AttributeError, Exception):
        # datasets module not available or cell_config() failed
        DEFAULT_CONFIG_FILE = None

    BTRACK_AVAILABLE = True
    
    # Check btrack version - 0.7.0 has known bugs with empty dict configuration
    try:
        btrack_version = btrack.__version__
        if btrack_version.startswith("0.7.0"):
            logger.info(
                f"btrack {btrack_version} detected. Using default cell config to avoid crashes."
            )
        elif btrack_version.startswith("0.6"):
            logger.info(f"btrack {btrack_version} detected (compatible version)")
    except AttributeError:
        pass  # Version not available
except ImportError as e:
    # Import failed - could be missing package or pydantic version conflict
    logger.debug(f"btrack import failed: {e}")
except Exception as e:
    # Other errors (e.g., pydantic version incompatibility)
    logger.warning(
        f"btrack import failed (possibly due to pydantic version conflict): {e}. "
        "btrack 0.6.x requires pydantic<2.0. Install with: "
        'uv pip install "btrack>=0.6.5,<0.7.0" "pydantic<2.0"'
    )


def track_cell(
    image: np.ndarray,
    out: np.ndarray,
    progress_callback: Callable | None = None,
    cancel_event=None,
    motion_model=None,
    object_model=None,
    hypothesis_model=None,
    tracking_updates=None,
    volume=None,
    max_search_radius: float | None = None,
    **tracker_kwargs,
) -> None:
    """Track cells across frames using BayesianTracker.

    Extracts regions per frame, converts them to trackable objects, and uses
    BayesianTracker with probabilistic models to maintain consistent cell IDs
    across frames. Writes results into ``out`` in-place.

    Args:
        image: 3D labeled array ``(T, H, W)`` (uint16) with cell segments.
        out: Preallocated integer array ``(T, H, W)`` to receive labeled IDs.
        progress_callback: Optional callable ``(t, total, msg)`` for progress.
        cancel_event: Optional threading.Event for cancellation support.
        motion_model: Optional btrack MotionModel. If None, uses default.
        object_model: Optional btrack ObjectModel. If None, uses default.
        hypothesis_model: Optional btrack HypothesisModel. If None, uses default.
        tracking_updates: Optional list of tracking update features to use.
            See btrack.constants.BayesianUpdateFeatures for options.
        volume: Optional imaging volume tuple. If None, auto-detected from image.
        max_search_radius: Maximum search radius for linking (pixels).
            If None, uses btrack default.
        **tracker_kwargs: Additional keyword arguments passed to BayesianTracker.

    Returns:
        None. Results are written to ``out``.

    Raises:
        ImportError: If btrack is not installed.
        ValueError: If ``image`` and ``out`` are not 3D or shapes differ.
    """
    if not BTRACK_AVAILABLE:
        raise ImportError(
            "btrack is not installed. Install it with: pip install btrack"
        )

    if image.ndim != 3 or out.ndim != 3:
        raise ValueError("image and out must be 3D arrays")

    if out.shape != image.shape:
        raise ValueError("image and out must have the same shape (T, H, W)")

    image = image.astype(np.uint16, copy=False)
    out = out.astype(np.uint16, copy=False)

    n_frames, height, width = image.shape

    # Use input labeled segmentation - ensure it's writable (not memory-mapped)
    # btrack expects labeled segmentation (each object has unique ID)
    # Make a copy if the array is read-only to avoid "buffer source array is read-only" error
    if not image.flags.writeable:
        labeled_segmentation = image.copy()
    else:
        labeled_segmentation = image

    # Set up imaging volume if not provided
    if volume is None:
        volume = ((0, width), (0, height), (-1e5, 1e5))  # 2D + dummy Z

    # Initialize BayesianTracker
    tracker = BayesianTracker(verbose=False, **tracker_kwargs)

    # Set volume (must be set before appending objects)
    tracker.volume = volume

    # Configure tracker BEFORE appending objects (as per btrack docs)
    # According to btrack docs: tracker.configure() -> tracker.append() -> tracker.track()
    # IMPORTANT: configure({}) with empty dict crashes btrack 0.7.0 due to uninitialized
    # motion model matrices. Always use a proper config file when available.
    # 
    # Check if we have custom models (motion/object/hypothesis) that require a custom config dict.
    # tracking_updates and max_search_radius can be set after configuration as overrides.
    has_custom_models = (
        motion_model is not None
        or object_model is not None
        or hypothesis_model is not None
    )
    
    if has_custom_models:
        # Custom models provided - build config dict
        config = {}
        if motion_model is not None:
            config["motion_model"] = motion_model
        if object_model is not None:
            config["object_model"] = object_model
        if hypothesis_model is not None:
            config["hypothesis_model"] = hypothesis_model
        tracker.configure(config)
    elif DEFAULT_CONFIG_FILE:
        # Use default cell config file (avoids empty dict crash)
        logger.debug("Using default cell config file: %s", DEFAULT_CONFIG_FILE)
        tracker.configure(DEFAULT_CONFIG_FILE)
    else:
        # No custom models and no default file - this will crash
        logger.error(
            "No config file available and no custom models provided. "
            "btrack requires a proper configuration to avoid crashes. "
            "Install btrack with example datasets or provide motion_model/object_model/hypothesis_model."
        )
        raise RuntimeError(
            "btrack configuration required. Either provide motion_model/object_model/hypothesis_model "
            "parameters, or ensure btrack.datasets.cell_config() is available. "
            "Using empty dict will crash in btrack 0.7.0."
        )

    # Set additional parameters after configuration (these override config file settings)
    if tracking_updates is not None:
        tracker.configuration.tracking_updates = tracking_updates
    if max_search_radius is not None:
        tracker.configuration.max_search_radius = max_search_radius

    logger.info("Converting segmentation to trackable objects...")

    # Convert segmentation to trackable objects
    # segmentation_to_objects expects T(Z)YX format
    objects = segmentation_to_objects(
        labeled_segmentation,
        properties=("area", "centroid"),
        use_weighted_centroid=False,
    )

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled during object conversion")
        return

    logger.info("Found %d objects across %d frames", len(objects), n_frames)

    # Append all objects to tracker (after configuration, as per btrack docs)
    tracker.append(objects)

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled before tracking")
        return

    # Run tracking using the standard track() method
    # According to btrack docs, this is the standard way to run tracking
    logger.info("Running Bayesian tracking...")
    
    try:
        tracker.track(step_size=100)
    except (SystemExit, KeyboardInterrupt):
        # Re-raise these
        raise
    except AttributeError as e:
        # Handle case where track() fails due to initialization issues
        error_msg = str(e)
        if "tracker_active" in error_msg or "NoneType" in error_msg:
            raise RuntimeError(
                f"btrack tracker failed to initialize properly: {error_msg}\n"
                f"Found {len(objects)} objects across {n_frames} frames.\n"
                "This may indicate an issue with the segmentation data or tracker configuration.\n"
                "Ensure segmentation contains valid labeled objects."
            ) from e
        else:
            # Re-raise other AttributeErrors
            raise
    except Exception as e:
        # Catch any other exceptions (including potential C library crashes)
        error_msg = str(e)
        if "Assertion" in error_msg or "Eigen" in error_msg:
            raise RuntimeError(
                f"btrack encountered a C library error: {error_msg}\n"
                f"Found {len(objects)} objects across {n_frames} frames.\n"
                "This may be a bug in btrack. Suggested workarounds:\n"
                "  1. Use IoU tracking instead (set tracking_method: iou in config)\n"
                "  2. Report this issue to btrack GitHub: https://github.com/quantumjot/btrack/issues"
            ) from e
        else:
            # Re-raise other exceptions
            raise
    
    logger.info("Tracking completed")

    if cancel_event and cancel_event.is_set():
        logger.info("Tracking cancelled during tracking")
        return

    # Get tracks
    tracks = tracker.tracks
    logger.info("Found %d tracks", len(tracks))

    # Map tracks back to segmentation
    # update_segmentation expects T(Z)YX format and returns relabeled segmentation
    tracked_segmentation = update_segmentation(
        labeled_segmentation,
        tracks,
        color_by="ID",
    )

    # Copy results to output array
    out[...] = tracked_segmentation

    logger.info("Bayesian tracking completed")
