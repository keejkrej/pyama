"""
Trace extraction processing service.
"""

import logging
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd

from pyama_core.io import MicroscopyMetadata
from pyama_core.processing.extraction import extract_trace_from_crops, ChannelFeatureConfig
from pyama_core.types.processing import (
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)
from pyama_core.processing.workflow.services.base import BaseProcessingService

logger = logging.getLogger(__name__)


class ExtractionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Extraction"

    def process_fov(
        self,
        metadata: MicroscopyMetadata,
        context: ProcessingContext,
        output_dir: Path,
        fov: int,
        cancel_event=None,
    ) -> None:
        context = ensure_context(context)
        base_name = metadata.base_name

        # Get params
        background_weight = 1.0
        erosion_size = 0
        if context.params:
            background_weight = context.params.get("background_weight", 1.0)
            try:
                background_weight = float(background_weight)
                background_weight = max(0.0, min(1.0, background_weight))
            except (ValueError, TypeError):
                background_weight = 1.0

            erosion_size = context.params.get("erosion_size", 0)
            try:
                erosion_size = max(0, int(erosion_size))
            except (ValueError, TypeError):
                erosion_size = 0

        fov_dir = output_dir / f"fov_{fov:03d}"

        if context.results is None:
            context.results = {}
        fov_paths = context.results.setdefault(fov, ensure_results_entry())

        # Check for crops H5 file
        crops_path = fov_paths.crops
        if crops_path is None:
            crops_path = fov_dir / f"{base_name}_fov_{fov:03d}_crops.h5"
        if not Path(crops_path).exists():
            raise FileNotFoundError(f"Crops H5 file not found: {crops_path}")

        traces_output_path = fov_dir / f"{base_name}_fov_{fov:03d}_traces.csv"
        if traces_output_path.exists():
            logger.info(
                "FOV %d: Traces CSV already exists, skipping extraction", fov
            )
            fov_paths.traces = traces_output_path
            return

        logger.info("FOV %d: Extracting features from cropped H5...", fov)

        # Compute times array
        def _compute_times(frame_count: int) -> np.ndarray:
            try:
                tp = getattr(metadata, "timepoints", None)
                if tp is not None and len(tp) == frame_count:
                    times_ms = np.asarray(tp, dtype=float)
                    return times_ms / 60000.0
            except Exception:
                pass
            return np.arange(frame_count, dtype=float)

        times = _compute_times(metadata.n_frames)

        # Build channel configs from context
        channel_configs: list[ChannelFeatureConfig] = []

        if context.channels:
            # Phase contrast features
            pc_features = context.channels.get_pc_features()
            if pc_features:
                pc_entry = fov_paths.pc
                if isinstance(pc_entry, tuple) and len(pc_entry) == 2:
                    pc_channel = int(pc_entry[0])
                    channel_configs.append(ChannelFeatureConfig(
                        channel_name=f"pc_ch_{pc_channel}",
                        background_name=None,
                        features=sorted(dict.fromkeys(pc_features)),
                        background_weight=0.0,  # No background for PC
                    ))

            # Fluorescence features
            fl_feature_map = context.channels.get_fl_feature_map()
            for ch, features in fl_feature_map.items():
                if features:
                    channel_configs.append(ChannelFeatureConfig(
                        channel_name=f"fl_ch_{ch}",
                        background_name=f"fl_ch_{ch}",
                        features=sorted(dict.fromkeys(features)),
                        background_weight=background_weight,
                    ))

        if not channel_configs:
            logger.warning("FOV %d: No channel configs, creating empty traces", fov)
            pd.DataFrame().to_csv(traces_output_path, index=False)
            fov_paths.traces = traces_output_path
            return

        logger.info(
            "FOV %d: Extracting from %d channel(s): %s",
            fov,
            len(channel_configs),
            ", ".join(cfg.channel_name for cfg in channel_configs),
        )

        # Single call to extract all features from all channels
        df = extract_trace_from_crops(
            crops_h5_path=crops_path,
            times=times,
            channel_configs=channel_configs,
            progress_callback=partial(self.progress_callback, fov),
            cancel_event=cancel_event,
            erosion_size=erosion_size,
        )

        if cancel_event and cancel_event.is_set():
            logger.info("FOV %d: Extraction cancelled", fov)
            return

        if df.empty:
            logger.info("FOV %d: No traces extracted, creating empty CSV", fov)
        else:
            df.insert(0, "fov", fov)
            df.sort_values(["cell", "frame", "time"], inplace=True)

        df.to_csv(traces_output_path, index=False, float_format="%.6f")
        fov_paths.traces = traces_output_path
        logger.info("FOV %d: Traces written to %s", fov, traces_output_path)
