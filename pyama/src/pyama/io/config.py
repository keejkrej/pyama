from pathlib import Path

import yaml

from pyama.types.processing import ProcessingConfig
import logging

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "processing_config.yaml"


def load_config(path: Path) -> ProcessingConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Processing config must contain a top-level mapping")
    return ProcessingConfig.from_dict(data)


def save_config(config: ProcessingConfig, path: Path) -> None:
    data = config.to_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)
    logger.info("Saved processing config to %s", path)


def ensure_config(config: ProcessingConfig | None) -> ProcessingConfig:
    if config is None:
        return ProcessingConfig()
    return config


def get_config_path(output_dir: Path) -> Path:
    return output_dir / CONFIG_FILENAME


__all__ = [
    "CONFIG_FILENAME",
    "ensure_config",
    "get_config_path",
    "load_config",
    "save_config",
]
