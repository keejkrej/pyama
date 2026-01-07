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

from pyama_core.types.processing import Channels

logger = logging.getLogger(__name__)


@dataclass
class ProcessingConfig:
    """Static configuration for processing pipeline.

    Attributes:
        channels: Channel selection and feature mapping.
        params: Processing parameters dict.
    """

    channels: Channels = field(default_factory=Channels)
    params: dict[str, Any] = field(default_factory=dict)

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with default."""
        return self.params.get(key, default)


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
    if channels_data is None:
        channels = Channels()
    else:
        channels = Channels.from_serialized(channels_data)

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
    data = {
        "channels": config.channels.to_raw(),
        "params": config.params,
    }

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

    # Ensure channels is normalized
    if config.channels is None:
        config.channels = Channels()
    else:
        config.channels.normalize()

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
    "CONFIG_FILENAME",
]
