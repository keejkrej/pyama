"""
Processing configuration - user-provided settings for the processing pipeline.

This module handles loading and saving processing configuration, which includes:
- channels: Which PC/FL channels to process and what features to extract
- params: Processing parameters (background_weight, mask_margin, etc.)

The config is static (user-provided) and does not track runtime state or output paths.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from pyama_core.types.processing import Channels, ProcessingConfig

logger = logging.getLogger(__name__)


def parse_channels_data(data: dict[str, Any]) -> Channels:
    """Parse channels configuration from a dictionary.

    Args:
        data: Dictionary containing 'pc' and 'fl' channel configuration.

    Returns:
        Channels object.

    Raises:
        ValidationError: If the configuration is invalid.
    """
    return Channels.model_validate(data)


def serialize_channels_data(channels: Channels) -> dict[str, Any]:
    """Serialize channels configuration to a dictionary.

    Args:
        channels: Channels object to serialize.

    Returns:
        Dictionary containing 'pc' and 'fl' channel configuration.
    """
    return channels.model_dump()


def load_config(path: Path) -> ProcessingConfig:
    """Load processing config from YAML file.

    Args:
        path: Path to config YAML file.

    Returns:
        ProcessingConfig object.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValidationError: If config file is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    return ProcessingConfig.model_validate(data)


def save_config(config: ProcessingConfig, path: Path) -> None:
    """Save processing config to YAML file.

    Args:
        config: ProcessingConfig to save.
        path: Path to write YAML file.
    """
    data = config.model_dump(exclude_defaults=True)

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
    return config


# Default config file name
CONFIG_FILENAME = "processing_config.yaml"


def get_config_path(output_dir: Path) -> Path:
    """Get default config file path for an output directory.

    Args:
        output_dir: Processing output directory.

    Returns:
        Path to processing_config.yaml in output_dir.
    """
    return output_dir / CONFIG_FILENAME


__all__ = [
    "load_config",
    "save_config",
    "ensure_config",
    "get_config_path",
    "parse_channels_data",
    "serialize_channels_data",
    "CONFIG_FILENAME",
]
