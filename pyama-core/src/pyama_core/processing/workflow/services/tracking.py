"""
Cell tracking processing service.
"""

from pathlib import Path
import numpy as np
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.tracking import track_cell
from pyama_core.io import MicroscopyMetadata, ProcessingConfig, ensure_config, naming
from numpy.lib.format import open_memmap


logger = logging.getLogger(__name__)


class TrackingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Tracking"

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
        seg_path = naming.seg_mask(output_dir, base_name, fov, pc_channel)
        seg_labeled_path = naming.seg_labeled(output_dir, base_name, fov, pc_channel)

        if not seg_path.exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_path}")

        # If output already exists, skip
        if seg_labeled_path.exists():
            logger.info("FOV %d: Tracked segmentation already exists, skipping", fov)
            return

        segmentation_data = np.load(seg_path, mmap_mode="r")
        n_frames, height, width = segmentation_data.shape

        logger.info("FOV %d: Starting cell tracking...", fov)
        seg_labeled_memmap = None
        try:
            seg_labeled_memmap = open_memmap(
                seg_labeled_path,
                mode="w+",
                dtype=np.uint16,
                shape=(n_frames, height, width),
            )
            track_cell(
                image=segmentation_data,
                out=seg_labeled_memmap,
                progress_callback=partial(self.progress_callback, fov),
                cancel_event=cancel_event,
            )
            seg_labeled_memmap.flush()
        except InterruptedError:
            if seg_labeled_memmap is not None:
                try:
                    del seg_labeled_memmap
                except Exception:
                    pass
            raise
        finally:
            if seg_labeled_memmap is not None:
                try:
                    del seg_labeled_memmap
                except Exception:
                    pass

        logger.info("FOV %d: Cell tracking completed", fov)
