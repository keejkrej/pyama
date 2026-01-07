"""
Cell tracking processing service.

**Channel-Conditional Behavior:**
- **Skipped** if no PC channel configured
- Requires segmentation masks from SegmentationService (seg_labeled.npy)
- Saves tracked segmentation: seg_tracked_ch_{N}.npy with consistent cell IDs
- Essential for any downstream analysis (cropping, extraction)
- Available algorithms: IoU-based (default), BTrack
- Logs warning "No PC channel configured, skipping tracking" when no PC
"""

from pathlib import Path
import numpy as np
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.tracking import get_tracker
from pyama_core.io import MicroscopyMetadata, ProcessingConfig, ensure_config, naming
from numpy.lib.format import open_memmap


logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    def __init__(self, method: str = "iou") -> None:
        super().__init__()
        self.name = "Tracking"
        self.method = method

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        config: ProcessingConfig,
        output_dir: Path,
        fov: int,
        cancel_event=None,
    ) -> None:
        config = ensure_config(config)
        base_name = metadata.base_name

        # Get PC channel from config
        pc_channel = config.channels.get_pc_channel()
        if pc_channel is None:
            logger.warning("FOV %d: No PC channel configured, skipping tracking", fov)
            return

        # Use naming module for paths
        seg_labeled_path = naming.seg_labeled(output_dir, base_name, fov, pc_channel)
        seg_tracked_path = naming.seg_tracked(output_dir, base_name, fov, pc_channel)

        if not seg_labeled_path.exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_labeled_path}")

        # If output already exists, skip
        if seg_tracked_path.exists():
            logger.info("FOV %d: Tracked segmentation already exists, skipping", fov)
            return

        seg_labeled_data = np.load(seg_labeled_path, mmap_mode="r")
        n_frames, height, width = seg_labeled_data.shape

        logger.info("FOV %d: Starting cell tracking...", fov)
        seg_tracked_memmap = open_memmap(
            seg_tracked_path,
            mode="w+",
            dtype=np.uint16,
            shape=(n_frames, height, width),
        )
        try:
            track_cell = get_tracker(self.method)
            track_cell(
                image=seg_labeled_data,
                out=seg_tracked_memmap,
                progress_callback=partial(self.progress_callback, fov),
                cancel_event=cancel_event,
            )
            seg_tracked_memmap.flush()
        finally:
            del seg_tracked_memmap

        logger.info("FOV %d: Cell tracking completed", fov)
