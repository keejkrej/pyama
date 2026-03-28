"""Services for revealing workspace and microscopy paths in the OS shell."""

import subprocess
import sys
from pathlib import Path
from typing import Protocol


class PathRevealService(Protocol):
    """Abstract path reveal operations used by status-bar widgets."""

    def reveal_path(self, path: Path) -> None:
        """Reveal the given path in the host operating system."""


class QtPathRevealService:
    """Default path reveal implementation for desktop platforms."""

    def reveal_path(self, path: Path) -> None:
        resolved_path = path.expanduser().resolve(strict=False)
        if sys.platform == "darwin":
            command = ["open", "-R", str(resolved_path)]
        elif sys.platform == "win32":
            command = ["explorer", f"/select,{resolved_path}"]
        else:
            target = resolved_path if resolved_path.is_dir() else resolved_path.parent
            command = ["xdg-open", str(target)]

        subprocess.Popen(command)


__all__ = ["PathRevealService", "QtPathRevealService"]
