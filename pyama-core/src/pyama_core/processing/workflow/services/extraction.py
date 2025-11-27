"""
Trace extraction processing service.
"""

import logging
from functools import partial
from pathlib import Path

import pandas as pd

from pyama_core.io import MicroscopyMetadata, ProcessingConfig, ensure_config, naming
from pyama_core.processing.extraction import extract_trace_from_crops, ChannelFeatureConfig
from pyama_core.processing.workflow.services.base import BaseProcessingService

logger = logging.getLogger(__name__)


class ExtractionService(BaseProcessingService):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Extraction"

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

        # Get params
        background_weight = config.get_param("background_weight", 1.0)
        try:
            background_weight = float(background_weight)
            background_weight = max(0.0, min(1.0, background_weight))
        except (ValueError, TypeError):
            background_weight = 1.0

        # Get channels from config
        pc_channel = config.channels.get_pc_channel()

        # Use naming module for paths
        crops_path = naming.crops_h5(output_dir, base_name, fov)
        traces_path = naming.traces_csv(output_dir, base_name, fov)

        if not crops_path.exists():
            raise FileNotFoundError(f"Crops H5 file not found: {crops_path}")

        if traces_path.exists():
            logger.info(
                "FOV %d: Traces CSV already exists, skipping extraction", fov
            )
            return

        logger.info("FOV %d: Extracting features from cropped H5...", fov)

        # Build channel configs from config
        channel_configs: list[ChannelFeatureConfig] = []

        # Phase contrast features
        pc_features = config.channels.get_pc_features()
        if pc_features and pc_channel is not None:
            channel_configs.append(ChannelFeatureConfig(
                channel_name=f"pc_ch_{pc_channel}",
                channel_id=pc_channel,
                background_name=None,
                features=sorted(dict.fromkeys(pc_features)),
                background_weight=0.0,  # No background for PC
            ))

        # Fluorescence features
        fl_feature_map = config.channels.get_fl_feature_map()
        for ch, features in fl_feature_map.items():
            if features:
                channel_configs.append(ChannelFeatureConfig(
                    channel_name=f"fl_ch_{ch}",
                    channel_id=ch,
                    background_name=f"fl_ch_{ch}",
                    features=sorted(dict.fromkeys(features)),
                    background_weight=background_weight,
                ))

        if not channel_configs:
            logger.warning("FOV %d: No channel configs, creating empty traces", fov)
            pd.DataFrame().to_csv(traces_path, index=False)
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
            channel_configs=channel_configs,
            progress_callback=partial(self.progress_callback, fov),
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info("FOV %d: Extraction cancelled", fov)
            return

        if df.empty:
            logger.info("FOV %d: No traces extracted, creating empty CSV", fov)
        else:
            df.insert(0, "fov", fov)
            df.sort_values(["cell", "frame"], inplace=True)

        df.to_csv(traces_path, index=False, float_format="%.6f")
        logger.info("FOV %d: Traces written to %s", fov, traces_path)
