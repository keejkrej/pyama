"""
Copy service for extracting frames from ND2 files to NPY format.
"""

from pathlib import Path
import logging
from functools import partial

from pyama_core.processing.workflow.services.base import BaseProcessingService
from pyama_core.processing.copying import copy_frames
from pyama_core.io import (
    MicroscopyMetadata,
    load_microscopy_file,
)
from pyama_core.types.processing import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)


logger = logging.getLogger(__name__)


class CopyingService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Copy"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
        cancel_event=None,
    ) -> None:
        context = ensure_context(context)
        img, _ = load_microscopy_file(metadata.file_path)
        fov_dir = output_dir / f"fov_{fov:03d}"
        fov_dir.mkdir(parents=True, exist_ok=True)
        T, H, W = metadata.n_frames, metadata.height, metadata.width
        base_name = metadata.base_name

        plan: list[tuple[str, int]] = []
        pc_selection = context.channels.pc
        if pc_selection is not None:
            plan.append(("pc", pc_selection.channel))
        for selection in context.channels.fl:
            plan.append(("fl", selection.channel))

        if not plan:
            logger.info("FOV %d: No channels selected to copy, skipping", fov)
            return

        for kind, ch in plan:
            logger.info("FOV %d: Processing %s channel %s", fov, kind.upper(), ch)
            # Simple, consistent filenames
            token = "pc" if kind == "pc" else "fl"
            ch_path = fov_dir / f"{base_name}_fov_{fov:03d}_{token}_ch_{ch}.npy"

            # If output already exists, record it and skip processing for this channel
            if Path(ch_path).exists():
                logger.info(
                    "FOV %d: %s channel %s already exists, skipping copy",
                    fov,
                    token.upper(),
                    ch,
                )
                fov_paths = context.results.setdefault(fov, ensure_results_entry())
                if kind == "fl":
                    fov_paths.fl.append((int(ch), Path(ch_path)))
                elif kind == "pc":
                    fov_paths.pc = (int(ch), Path(ch_path))
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

            fov_paths = context.results.setdefault(fov, ensure_results_entry())
            if kind == "fl":
                fov_paths.fl.append((int(ch), Path(ch_path)))
            elif kind == "pc":
                fov_paths.pc = (int(ch), Path(ch_path))

        logger.info(
            "FOV %d: Copy completed to %s (channels=%d)",
            fov,
            fov_dir,
            len(plan),
        )
