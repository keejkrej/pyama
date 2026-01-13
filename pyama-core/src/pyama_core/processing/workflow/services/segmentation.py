"""
Segmentation (formerly binarization) service.

**Channel-Conditional Behavior:**
- **Skipped** if no PC channel configured
- Requires phase contrast channel for cell detection
- Saves labeled segmentation masks: seg_labeled_ch_{N}.npy
- Essential prerequisite for tracking (needs seg_labeled input)
- Available algorithms: LOG-STD (default), CellPose
- Logs warning "No PC channel configured, skipping segmentation" when no PC
"""

from pathlib import Path
import numpy as np
from functools import partial
import logging

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.io import MicroscopyMetadata, ProcessingConfig, ensure_config, naming
from pyama_core.processing.segmentation import get_segmenter
from numpy.lib.format import open_memmap


logger = logging.getLogger(__name__)


class SegmentationService(BaseProcessingService):
    def __init__(self, method: str = "logstd") -> None:
        super().__init__()
        self.name = "Segmentation"
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
            logger.warning(
                "FOV %d: No PC channel configured, skipping segmentation", fov
            )
            return

        # Use naming module for paths
        pc_path = naming.pc_stack(output_dir, base_name, fov, pc_channel)
        seg_labeled_path = naming.seg_labeled(output_dir, base_name, fov, pc_channel)

        if not pc_path.exists():
            raise FileNotFoundError(f"Phase contrast file not found: {pc_path}")

        # If output already exists, skip
        if seg_labeled_path.exists():
            logger.info("FOV %d: Segmentation already exists, skipping", fov)
            return

        logger.info("FOV %d: Loading phase contrast data...", fov)
        phase_contrast_data = np.load(pc_path, mmap_mode="r")

        if phase_contrast_data.ndim != 3:
            raise ValueError(
                f"Unexpected dims for phase contrast data: {phase_contrast_data.shape}"
            )

        logger.info("FOV %d: Applying segmentation...", fov)
        seg_labeled_memmap = open_memmap(
            seg_labeled_path,
            mode="w+",
            dtype=np.uint16,
            shape=phase_contrast_data.shape,
        )
        try:
            segment_cell = get_segmenter(self.method)
            segment_cell(
                phase_contrast_data,
                seg_labeled_memmap,
                progress_callback=partial(self.progress_callback, fov),
                cancel_event=cancel_event,
            )
            seg_labeled_memmap.flush()
        finally:
            del seg_labeled_memmap

        logger.info("FOV %d: Segmentation completed", fov)
