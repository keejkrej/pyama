"""
Background estimation processing service.

This service estimates background fluorescence using tiled interpolation.
The estimated background is saved for later correction processing.
"""

from pathlib import Path
import numpy as np
from numpy.lib.format import open_memmap
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.background import estimate_background
from pyama_core.io import MicroscopyMetadata, ProcessingConfig, ensure_config, naming


logger = logging.getLogger(__name__)


class BackgroundEstimationService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Background Estimation"

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

        # Get channels from config
        pc_channel = config.channels.get_pc_channel()
        fl_channels = config.channels.get_fl_channels()

        if not fl_channels:
            logger.info(
                "FOV %d: No fluorescence channels, skipping background estimation", fov
            )
            return

        if pc_channel is None:
            logger.warning(
                "FOV %d: No PC channel configured, skipping background estimation", fov
            )
            return

        # Load segmentation once
        seg_path = naming.seg_mask(output_dir, base_name, fov, pc_channel)
        if not seg_path.exists():
            raise FileNotFoundError(f"Segmentation data not found: {seg_path}")

        logger.info("FOV %d: Loading segmentation data...", fov)
        segmentation_data = open_memmap(seg_path, mode="r")

        for ch in fl_channels:
            fl_path = naming.fl_stack(output_dir, base_name, fov, ch)
            background_path = naming.fl_background(output_dir, base_name, fov, ch)

            # If output exists, skip this channel
            if background_path.exists():
                logger.info(
                    "FOV %d: Background for channel %d already exists, skipping",
                    fov,
                    ch,
                )
                continue

            if not fl_path.exists():
                logger.warning(
                    "FOV %d: Fluorescence data not found for channel %d, skipping",
                    fov,
                    ch,
                )
                continue

            logger.info("FOV %d: Loading fluorescence data for channel %d...", fov, ch)
            fluor_data = open_memmap(fl_path, mode="r")

            if fluor_data.ndim != 3:
                raise ValueError(
                    f"Unexpected fluorescence data dims: {fluor_data.shape}"
                )
            n_frames, height, width = fluor_data.shape

            if segmentation_data.shape != (n_frames, height, width):
                raise ValueError(
                    f"Shape mismatch: segmentation {segmentation_data.shape} vs "
                    f"fluorescence {fluor_data.shape}"
                )

            background_memmap = open_memmap(
                background_path,
                mode="w+",
                dtype=np.float32,
                shape=(n_frames, height, width),
            )

            logger.info(
                "FOV %d: Starting background estimation for channel %d...", fov, ch
            )
            try:
                estimate_background(
                    fluor_data.astype(np.float32),
                    segmentation_data,
                    background_memmap,
                    progress_callback=partial(self.progress_callback, fov),
                    cancel_event=cancel_event,
                )
                background_memmap.flush()
            except InterruptedError:
                if background_memmap is not None:
                    del background_memmap
                raise

            logger.info("FOV %d: Cleaning up channel %d...", fov, ch)
            if background_memmap is not None:
                del background_memmap

        logger.info(
            "FOV %d: Background estimation completed for %d channel(s)",
            fov,
            len(fl_channels),
        )
