"""Microscopy file loading service."""

import logging
from pathlib import Path

from pyama_core.io.microscopy import MicroscopyMetadata, load_microscopy_file

logger = logging.getLogger(__name__)


class MicroscopyServiceError(Exception):
    """Raised when a microscopy operation fails."""

    pass


class MicroscopyService:
    """Service for microscopy file operations."""

    def load_metadata(self, file_path: str) -> MicroscopyMetadata:
        """Load microscopy file and return metadata.

        Args:
            file_path: Path to microscopy file (ND2, CZI, TIFF)

        Returns:
            MicroscopyMetadata object with file info

        Raises:
            MicroscopyServiceError: If file not found or loading fails
        """
        path = Path(file_path)

        if not path.exists():
            raise MicroscopyServiceError(f"File not found: {file_path}")

        try:
            _, metadata = load_microscopy_file(path)
            logger.info("Loaded microscopy file: %s", file_path)
            return metadata
        except Exception as e:
            logger.exception("Failed to load microscopy file: %s", file_path)
            raise MicroscopyServiceError(f"Failed to load microscopy file: {e}") from e
