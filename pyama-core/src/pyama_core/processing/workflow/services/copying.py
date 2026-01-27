"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.copying import copy_frames
from pyama_core.types.processing import ProcessingConfig
from pyama_core.io import (
    MicroscopyMetadata,
    load_microscopy_file,
    naming,
    ensure_config,
)


logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Copy"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        config: ProcessingConfig,
        output_dir: Path,
        fov: int,
        cancel_event=None,
    ) -> None:
        config = ensure_config(config)
        img, _ = load_microscopy_file(metadata.file_path)
        fov_path = naming.fov_dir(output_dir, fov)
        fov_path.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        plan: list[tuple[str, int]] = []
        pc_selection = config.channels.pc
        if pc_selection is not None:
            plan.append(("pc", pc_selection.channel))
        for selection in config.channels.fl:
            plan.append(("fl", selection.channel))

        if not plan:
            logger.info("FOV %d: No channels selected to copy, skipping", fov)
            return

        for kind, ch in plan:
            logger.info("FOV %d: Processing %s channel %s", fov, kind.upper(), ch)

            if kind == "pc":
                ch_path = naming.pc_stack(output_dir, base_name, fov, ch)
            else:
                ch_path = naming.fl_stack(output_dir, base_name, fov, ch)

            # If output already exists, skip
            if ch_path.exists():
                logger.info(
                    "FOV %d: %s channel %s already exists, skipping copy",
                    fov,
                    kind.upper(),
                    ch,
                )
                continue

            # Copy frames using the functional API
            logger.info("FOV %d: Copying %s channel %s...", fov, kind.upper(), ch)
            success = copy_frames(
                img=img,
                fov=fov,
                channel=ch,
                n_frames=T,
                output_path=ch_path,
                height=H,
                width=W,
                progress_callback=partial(self.progress_callback, fov),
                cancel_event=cancel_event,
            )

            if not success:
                logger.info("FOV %d: Copying cancelled for channel %s", fov, ch)
                return

        logger.info(
            "FOV %d: Copy completed to %s (channels=%d)",
            fov,
            fov_path,
            len(plan),
        )
