"""Client for the stdio-based pyama RPC server."""

import json
import logging
from pathlib import Path
from queue import Queue
from threading import Lock, Thread
import time
from typing import Callable
from uuid import uuid4

from pyama.rpc.codec import from_wire, to_wire
from pyama.rpc.process import spawn_rpc_server_process

logger = logging.getLogger(__name__)


class PyamaRpcClient:
    """Request/response client with server notification support."""

    def __init__(self, *, cwd: Path | None = None) -> None:
        self._process = spawn_rpc_server_process(cwd=cwd)
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("Failed to start RPC server stdio pipes")
        self._stdin = self._process.stdin
        self._stdout = self._process.stdout
        self._stderr = self._process.stderr
        self._lock = Lock()
        self._pending: dict[str, Queue] = {}
        self._notification_handler: Callable[[str, object], None] | None = None
        self._closed = False
        self._reader_thread = Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        self._stderr_thread = Thread(target=self._stderr_loop, daemon=True)
        self._stderr_thread.start()
        self.request("system.ping", {})

    def set_notification_handler(
        self,
        handler: Callable[[str, object], None] | None,
    ) -> None:
        self._notification_handler = handler

    def request(self, method: str, params: dict[str, object]) -> object:
        if self._closed:
            raise RuntimeError("RPC client is closed")
        request_id = uuid4().hex
        response_queue: Queue = Queue()
        with self._lock:
            self._pending[request_id] = response_queue
            payload = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": to_wire(params),
                }
            )
            self._stdin.write(f"{payload}\n")
            self._stdin.flush()
        message = response_queue.get(timeout=120.0)
        if "error" in message:
            error = message["error"]
            if isinstance(error, dict):
                raise RuntimeError(str(error.get("message", "RPC request failed")))
            raise RuntimeError("RPC request failed")
        return from_wire(message.get("result"))

    def close(self) -> None:
        if self._closed:
            return
        try:
            self.request("system.shutdown", {})
        except Exception:
            logger.debug("RPC shutdown request failed", exc_info=True)
        self._closed = True
        try:
            self._stdin.close()
        except Exception:
            pass
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if self._process.poll() is not None:
                break
            time.sleep(0.05)
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except Exception:
                self._process.kill()

    def _reader_loop(self) -> None:
        try:
            for line in self._stdout:
                line = line.strip()
                if not line:
                    continue
                message = json.loads(line)
                response_id = message.get("id")
                if response_id is not None:
                    with self._lock:
                        queue = self._pending.pop(str(response_id), None)
                    if queue is not None:
                        queue.put(message)
                    continue
                method = message.get("method")
                if not isinstance(method, str):
                    continue
                if self._notification_handler is not None:
                    params = from_wire(message.get("params"))
                    self._notification_handler(method, params)
        except Exception:
            logger.exception("RPC stdout reader failed")

    def _stderr_loop(self) -> None:
        if self._stderr is None:
            return
        try:
            for line in self._stderr:
                text = line.rstrip()
                if text:
                    logger.debug("rpc-server: %s", text)
        except Exception:
            logger.debug("RPC stderr reader failed", exc_info=True)


__all__ = ["PyamaRpcClient"]
