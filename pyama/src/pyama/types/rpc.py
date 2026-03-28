"""RPC protocol support types for pyama."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RpcFileHandle:
    """Typed reference to a server-generated local artifact."""

    path: Path
    kind: str
    format: str


@dataclass(frozen=True, slots=True)
class RpcTableHandle(RpcFileHandle):
    """Reference to a tabular artifact."""


@dataclass(frozen=True, slots=True)
class RpcJsonHandle(RpcFileHandle):
    """Reference to a JSON artifact."""


@dataclass(frozen=True, slots=True)
class RpcArrayHandle(RpcFileHandle):
    """Reference to an array artifact."""


@dataclass(frozen=True, slots=True)
class RpcError:
    """Structured RPC error payload."""

    code: str
    message: str
    data: dict[str, object] | None = None


__all__ = [
    "RpcArrayHandle",
    "RpcError",
    "RpcFileHandle",
    "RpcJsonHandle",
    "RpcTableHandle",
]
