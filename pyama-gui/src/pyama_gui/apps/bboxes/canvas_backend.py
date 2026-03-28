"""Web-canvas backend for the Align tab."""

import asyncio
import base64
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from websockets.asyncio.server import serve

from pyama.io import get_microscopy_frame, load_microscopy_file

logger = logging.getLogger(__name__)

_SAMPLE_SIZE = 2048
_DEFAULT_DOMAIN = {"min": 0, "max": 65535}
_BACKEND_HOST = "127.0.0.1"


def _sampled_values(values: np.ndarray) -> np.ndarray:
    flat = np.asarray(values).reshape(-1)
    if flat.size == 0:
        return np.array([0], dtype=np.uint16)
    if flat.size <= _SAMPLE_SIZE:
        return np.sort(flat)
    indices = np.linspace(0, flat.size - 1, _SAMPLE_SIZE, dtype=np.int64)
    return np.sort(flat[indices])


def _percentile(values: np.ndarray, q: float) -> int:
    sampled = _sampled_values(values)
    index = int(max(0.0, min(1.0, q)) * (sampled.size - 1))
    return int(sampled[index])


def _auto_contrast(values: np.ndarray) -> dict[str, int]:
    if values.size == 0:
        return {"min": 0, "max": 1}
    minimum = _percentile(values, 0.001)
    maximum = _percentile(values, 0.999)
    return {"min": minimum, "max": max(minimum + 1, maximum)}


def _contrast_domain(values: np.ndarray) -> dict[str, int]:
    if values.size == 0:
        return dict(_DEFAULT_DOMAIN)

    dtype = values.dtype
    if np.issubdtype(dtype, np.integer):
        info = np.iinfo(dtype)
        return {"min": int(info.min), "max": int(info.max)}

    minimum = int(np.floor(float(np.min(values))))
    maximum = int(np.ceil(float(np.max(values))))
    if minimum == maximum:
        maximum = minimum + 1
    return {"min": minimum, "max": maximum}


def _normalize_contrast(
    contrast: dict[str, int] | None,
    *,
    domain: dict[str, int],
) -> dict[str, int]:
    if contrast is None:
        raise ValueError("contrast window is required")

    domain_min = int(domain["min"])
    domain_max = int(domain["max"])
    minimum = max(domain_min, min(int(contrast["min"]), domain_max - 1))
    maximum = max(minimum + 1, min(int(contrast["max"]), domain_max))
    return {"min": minimum, "max": maximum}


def _apply_contrast(values: np.ndarray, contrast: dict[str, int]) -> np.ndarray:
    minimum = float(contrast["min"])
    maximum = float(max(contrast["max"], contrast["min"] + 1))
    normalized = np.clip(
        (values.astype(np.float32) - minimum) / max(1.0, maximum - minimum),
        0.0,
        1.0,
    )
    return np.round(normalized * 255.0).astype(np.uint8)


def _normalize_source(payload: Any) -> Path:
    if not isinstance(payload, dict):
        raise ValueError("Invalid source payload")
    path = payload.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("Invalid source payload")
    return Path(path)


def _normalize_request(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid frame request payload")
    return {
        "pos": int(payload["pos"]),
        "channel": int(payload["channel"]),
        "time": int(payload["time"]),
        "z": int(payload["z"]),
    }


def _ok_response(message_id: str, message_type: str, payload: Any) -> str:
    return json.dumps({"id": message_id, "type": message_type, "payload": payload})


def _error_response(message_id: str, message: str) -> str:
    return _ok_response(message_id, "error", {"message": message})


class AlignCanvasBackend:
    """Load microscopy frames for the embedded web canvas."""

    def load_frame(
        self,
        source_path: Path,
        request: dict[str, int],
        contrast: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        reader = None
        try:
            reader, _metadata = load_microscopy_file(source_path)
            frame = np.asarray(
                get_microscopy_frame(
                    reader,
                    position=int(request["pos"]),
                    channel=int(request["channel"]),
                    time=int(request["time"]),
                    z=int(request["z"]),
                )
            )
        finally:
            if reader is not None and not reader.closed:
                reader.close()

        domain = _contrast_domain(frame)
        suggested = _auto_contrast(frame)
        applied = _normalize_contrast(contrast or suggested, domain=domain)
        display = _apply_contrast(frame, applied)
        height, width = display.shape
        return {
            "width": int(width),
            "height": int(height),
            "dataBase64": base64.b64encode(display.tobytes()).decode("ascii"),
            "pixelType": "uint8",
            "contrastDomain": domain,
            "suggestedContrast": suggested,
            "appliedContrast": applied,
        }


class AlignCanvasBackendServer:
    """Small websocket server that matches the `view` web-canvas protocol."""

    def __init__(
        self,
        backend: AlignCanvasBackend | None = None,
        *,
        host: str = _BACKEND_HOST,
        port: int = 0,
    ) -> None:
        self._backend = backend or AlignCanvasBackend()
        self._host = host
        self._port = port
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready = threading.Event()
        self._started = threading.Event()
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="pyama-align"
        )
        self._bound_port: int | None = None
        self._startup_error: Exception | None = None

    @property
    def url(self) -> str:
        if self._bound_port is None:
            raise RuntimeError("Align canvas backend server has not started")
        return f"ws://{self._host}:{self._bound_port}"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            name="pyama-align-backend",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=10.0)
        if self._startup_error is not None:
            raise RuntimeError(
                "Failed to start align canvas backend"
            ) from self._startup_error
        if not self._started.is_set():
            raise RuntimeError("Timed out while starting align canvas backend")

    def stop(self) -> None:
        loop = self._loop
        stop_event = self._stop_event
        if loop is not None and stop_event is not None:
            loop.call_soon_threadsafe(stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(self._serve())
        except Exception as error:  # noqa: BLE001
            self._startup_error = error
            logger.exception("Failed to run align canvas backend server")
            self._ready.set()
        finally:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.close()
            self._loop = None
            self._stop_event = None

    async def _serve(self) -> None:
        assert self._stop_event is not None
        async with serve(self._handle_connection, self._host, self._port) as server:
            socket = server.sockets[0] if server.sockets else None
            if socket is None:
                raise RuntimeError("Align canvas backend failed to bind a socket")
            self._bound_port = int(socket.getsockname()[1])
            self._started.set()
            self._ready.set()
            await self._stop_event.wait()

    async def _handle_connection(self, websocket: Any) -> None:
        async for message in websocket:
            if not isinstance(message, str):
                continue
            response = await self._handle_request(message)
            if response is not None:
                await websocket.send(response)

    async def _handle_request(self, text: str) -> str | None:
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(envelope, dict):
            return None

        message_id = str(envelope.get("id", ""))
        message_type = envelope.get("type")
        payload = envelope.get("payload")
        if not message_id or not isinstance(message_type, str):
            return None

        loop = asyncio.get_running_loop()
        try:
            if message_type != "load_frame":
                return _error_response(message_id, "Unsupported request type")
            if not isinstance(payload, dict):
                raise ValueError("Invalid load_frame payload")
            source_path = _normalize_source(payload.get("source"))
            request = _normalize_request(payload.get("request"))
            contrast_payload = payload.get("contrast")
            contrast = None
            if isinstance(contrast_payload, dict):
                contrast = {
                    "min": int(contrast_payload["min"]),
                    "max": int(contrast_payload["max"]),
                }
            result = await loop.run_in_executor(
                self._executor,
                self._backend.load_frame,
                source_path,
                request,
                contrast,
            )
            return _ok_response(message_id, "load_frame_result", result)
        except Exception as error:  # noqa: BLE001
            logger.exception("Failed to handle align canvas request")
            return _error_response(message_id, str(error))
