"""
Processing configuration - user-provided settings for the processing pipeline.

This module handles loading and saving processing configuration, which includes:
- channels: Which PC/FL channels to process and what features to extract
- params: Processing parameters (background_weight, mask_margin, etc.)

The config is static (user-provided) and does not track runtime state or output paths.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from pyama_core.types.processing import Channels, ChannelSelection

logger = logging.getLogger(__name__)


@dataclass
class ProcessingConfig:
    """Static configuration for processing pipeline.

    Attributes:
        channels: Channel selection and feature mapping.
        params: Processing parameters dict.
    """

    channels: Channels | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with default."""
        return self.params.get(key, default)


def _parse_channel_selection(data: dict[str, Any]) -> ChannelSelection:
    """Parse a channel selection from a dictionary."""
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict for channel selection, got {type(data)}")

    channel = data.get("channel")
    if not isinstance(channel, int):
        raise ValueError(f"Invalid channel ID: {channel}")

    features = data.get("features", [])
    if not isinstance(features, list):
        raise ValueError(f"features must be a list, got {type(features)}")

    return ChannelSelection(channel=channel, features=features)


def _serialize_channel_selection(selection: ChannelSelection) -> dict[str, Any]:
    """Serialize a channel selection to a dictionary."""
    return {
        "channel": selection.channel,
        "features": list(selection.features),
    }


def parse_channels_data(data: dict[str, Any]) -> Channels:
    """Parse channels configuration from a dictionary.

    Args:
        data: Dictionary containing 'pc' and 'fl' channel configuration.

    Returns:
        Channels object.

    Raises:
        ValueError: If the configuration is invalid.
    """
    # Parse PC
    pc_data = data.get("pc")
    if pc_data is None:
        raise ValueError("channels.pc is required")
    pc = _parse_channel_selection(pc_data)

    # Parse FL
    fl_data = data.get("fl", [])
    if not isinstance(fl_data, list):
        raise ValueError("channels.fl must be a list")

    fl = [_parse_channel_selection(item) for item in fl_data]

    return Channels(pc=pc, fl=fl)


def serialize_channels_data(channels: Channels) -> dict[str, Any]:
    """Serialize channels configuration to a dictionary.

    Args:
        channels: Channels object to serialize.

    Returns:
        Dictionary containing 'pc' and 'fl' channel configuration.
    """
    return {
        "pc": _serialize_channel_selection(channels.pc),
        "fl": [_serialize_channel_selection(sel) for sel in channels.fl],
    }


def load_config(path: Path) -> ProcessingConfig:
    """Load processing config from YAML file.

    Args:
        path: Path to config YAML file.

    Returns:
        ProcessingConfig object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    # Parse channels
    channels_data = data.get("channels")
    channels = None
    if channels_data is not None:
        if not isinstance(channels_data, dict):
            raise ValueError("channels must be a dictionary")
        channels = parse_channels_data(channels_data)

    # Parse params
    params = data.get("params", {})
    if params is None:
        params = {}

    return ProcessingConfig(channels=channels, params=params)


def save_config(config: ProcessingConfig, path: Path) -> None:
    """Save processing config to YAML file.

    Args:
        config: ProcessingConfig to save.
        path: Path to write YAML file.
    """
    data: dict[str, Any] = {
        "params": config.params,
    }

    if config.channels:
        data["channels"] = serialize_channels_data(config.channels)

    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)

    logger.info("Saved processing config to %s", path)


def ensure_config(config: ProcessingConfig | None) -> ProcessingConfig:
    """Ensure config is valid, creating default if None.

    Args:
        config: Config to validate or None.

    Returns:
        Valid ProcessingConfig.
    """
    if config is None:
        return ProcessingConfig()

    # Ensure params is a dict
    if config.params is None:
        config.params = {}

    return config


# Default config file name
CONFIG_FILENAME = "processing_config.yaml"


def config_path(output_dir: Path) -> Path:
    """Get default config file path for an output directory.

    Args:
        output_dir: Processing output directory.

    Returns:
        Path to processing_config.yaml in output_dir.
    """
    return output_dir / CONFIG_FILENAME


__all__ = [
    "ProcessingConfig",
    "load_config",
    "save_config",
    "ensure_config",
    "config_path",
    "parse_channels_data",
    "serialize_channels_data",
    "CONFIG_FILENAME",
]
