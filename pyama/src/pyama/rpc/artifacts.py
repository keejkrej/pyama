"""Server-generated artifact helpers for large RPC payloads."""

import json
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

import pandas as pd

from pyama.types import RpcJsonHandle, RpcTableHandle


class ArtifactStore:
    """Own temporary artifacts created by the RPC server."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="pyama-rpc-"))

    def write_dataframe(self, df: pd.DataFrame, *, kind: str) -> RpcTableHandle:
        path = self.root / f"{uuid4().hex}.pkl"
        df.to_pickle(path)
        return RpcTableHandle(path=path, kind=kind, format="pickle")

    def write_json(self, payload: object, *, kind: str) -> RpcJsonHandle:
        path = self.root / f"{uuid4().hex}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        return RpcJsonHandle(path=path, kind=kind, format="json")

    def cleanup(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


def load_table_handle(handle: RpcTableHandle) -> pd.DataFrame:
    if handle.format != "pickle":
        raise ValueError(f"Unsupported table artifact format: {handle.format}")
    table = pd.read_pickle(handle.path)
    if not isinstance(table, pd.DataFrame):
        raise TypeError(f"Expected DataFrame artifact, got {type(table)!r}")
    return table


def load_json_handle(handle: RpcJsonHandle) -> object:
    if handle.format != "json":
        raise ValueError(f"Unsupported JSON artifact format: {handle.format}")
    with handle.path.open("r", encoding="utf-8") as source:
        return json.load(source)


__all__ = ["ArtifactStore", "load_json_handle", "load_table_handle"]
