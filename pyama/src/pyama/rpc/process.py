"""Process helpers for the pyama RPC server."""

import os
from pathlib import Path
import subprocess
import sys


def spawn_rpc_server_process(
    *,
    cwd: Path | None = None,
) -> subprocess.Popen[str]:
    """Start the stdio RPC child process."""
    env = dict(os.environ)
    return subprocess.Popen(
        [sys.executable, "-m", "pyama.rpc.server"],
        cwd=None if cwd is None else str(cwd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
        env=env,
    )


__all__ = ["spawn_rpc_server_process"]
