"""
Cropping service for extracting cell bounding box crops from tracked segmentation.

**Channel-Conditional Behavior:**
- **Skipped** if no PC channel configured (needs tracked segmentation masks)
- Works with PC-only data: crops PC channel data only
- With FL configured: crops both PC and FL channels, applies background if available
- Creates HDF5 with /cell_XXXX/ structure containing masks, channels/, and backgrounds/
- Essential for extraction step - provides cropped regions for efficient feature extraction
"""

from pathlib import Path
import numpy as np
import h5py
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.cropping import crop_cells
from pyama_core.types.processing import ProcessingConfig
from pyama_core.types.microscopy import MicroscopyMetadata
from pyama_core.io import ensure_config, naming


logger = logging.getLogger(__name__)


class CroppingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Cropping"

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

        if pc_channel is None:
            logger.warning("FOV %d: No PC channel configured, skipping cropping", fov)
            return

        # Use naming module for paths
        seg_tracked_path = naming.seg_tracked(output_dir, base_name, fov, pc_channel)
        crops_path = naming.crops_h5(output_dir, base_name, fov)

        if not seg_tracked_path.exists():
            raise FileNotFoundError(
                f"Tracked segmentation not found: {seg_tracked_path}"
            )

        # If output already exists, skip
        if crops_path.exists():
            logger.info("FOV %d: Crops already exist, skipping", fov)
            return

        logger.info("FOV %d: Loading tracked segmentation...", fov)
        seg_tracked_data = np.load(seg_tracked_path, mmap_mode="r")

        # Gather channel data to crop
        channels: dict[str, np.ndarray] = {}
        backgrounds: dict[str, np.ndarray] = {}

        # Phase contrast
        pc_path = naming.pc_stack(output_dir, base_name, fov, pc_channel)
        if pc_path.exists():
            logger.info("FOV %d: Loading phase contrast channel %d...", fov, pc_channel)
            channels[f"pc_ch_{pc_channel}"] = np.load(pc_path, mmap_mode="r")

        # Fluorescence channels and backgrounds
        for fl_ch in fl_channels:
            fl_path = naming.fl_stack(output_dir, base_name, fov, fl_ch)
            bg_path = naming.fl_background(output_dir, base_name, fov, fl_ch)

            if fl_path.exists():
                logger.info("FOV %d: Loading fluorescence channel %d...", fov, fl_ch)
                channels[f"fl_ch_{fl_ch}"] = np.load(fl_path, mmap_mode="r")

            if bg_path.exists():
                logger.info("FOV %d: Loading background for channel %d...", fov, fl_ch)
                backgrounds[f"fl_ch_{fl_ch}"] = np.load(bg_path, mmap_mode="r")

        # Get cropping parameters from config
        padding = config.params.crop_padding
        mask_margin = config.params.mask_margin
        min_frames = config.params.min_frames
        border_margin = config.params.border_margin

        logger.info(
            "FOV %d: Cropping cells (padding=%d, mask_margin=%d, min_frames=%d, border_margin=%d)...",
            fov,
            padding,
            mask_margin,
            min_frames,
            border_margin,
        )

        # Extract crops
        cell_crops = crop_cells(
            labeled=seg_tracked_data,
            channels=channels,
            backgrounds=backgrounds,
            padding=padding,
            mask_margin=mask_margin,
            min_frames=min_frames,
            border_margin=border_margin,
            progress_callback=partial(self.progress_callback, fov),
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info("FOV %d: Cropping cancelled", fov)
            return

        if not cell_crops:
            logger.warning("FOV %d: No cells found to crop", fov)
            return

        # Save to HDF5
        logger.info("FOV %d: Saving %d cells to HDF5...", fov, len(cell_crops))
        self._save_crops_h5(crops_path, cell_crops, cancel_event)

        if cancel_event and cancel_event.is_set():
            # Clean up partial file
            try:
                crops_path.unlink(missing_ok=True)
            except Exception:
                pass
            logger.info("FOV %d: Cropping cancelled during save", fov)
            return

        logger.info("FOV %d: Cropping completed, saved %d cells", fov, len(cell_crops))

    def _save_crops_h5(self, path: Path, cell_crops, cancel_event=None) -> None:
        """Save cell crops to HDF5 file.

        See docs/reference/file-formats.md for complete HDF5 structure documentation.

        Structure (summary):
            /cell_XXXX/
                bboxes     (n_frames, 5) [t, y0, x0, y1, x1] int32
                frames     (n_frames,) frame indices int32
                masks/     (h, w) boolean masks per frame
                channels/  cropped image data (pc_ch_*, fl_ch_*)
                backgrounds/ background data for FL channels (optional)
        """
        with h5py.File(path, "w") as f:
            for crop in cell_crops:
                if cancel_event and cancel_event.is_set():
                    return

                cell_grp = f.create_group(f"cell_{crop.cell_id:04d}")

                # Save bboxes and frames
                cell_grp.create_dataset(
                    "bboxes", data=crop.bboxes, dtype=np.int32, compression="gzip"
                )
                cell_grp.create_dataset(
                    "frames", data=crop.frames, dtype=np.int32, compression="gzip"
                )

                # Save masks
                masks_grp = cell_grp.create_group("masks")
                for i, (frame_idx, mask) in enumerate(zip(crop.frames, crop.masks)):
                    masks_grp.create_dataset(
                        f"frame_{frame_idx:04d}",
                        data=mask,
                        dtype=bool,
                        compression="gzip",
                    )

                # Save channel crops
                if crop.crops:
                    channels_grp = cell_grp.create_group("channels")
                    for ch_name, ch_crops in crop.crops.items():
                        ch_grp = channels_grp.create_group(ch_name)
                        for frame_idx, ch_crop in zip(crop.frames, ch_crops):
                            ch_grp.create_dataset(
                                f"frame_{frame_idx:04d}",
                                data=ch_crop,
                                compression="gzip",
                            )

                # Save background crops
                if crop.backgrounds:
                    backgrounds_grp = cell_grp.create_group("backgrounds")
                    for ch_name, bg_crops in crop.backgrounds.items():
                        bg_grp = backgrounds_grp.create_group(ch_name)
                        for frame_idx, bg_crop in zip(crop.frames, bg_crops):
                            bg_grp.create_dataset(
                                f"frame_{frame_idx:04d}",
                                data=bg_crop,
                                compression="gzip",
                            )
