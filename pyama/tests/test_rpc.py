from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import time

import pandas as pd
import pytest

from pyama.rpc.client import PyamaRpcClient
from pyama.rpc.codec import from_wire, to_wire
from pyama.tasks import (
    ModelFitTaskRequest,
    get_task,
    list_tasks,
    shutdown_backend,
    start_rpc_backend,
    submit_model_fit,
    subscribe,
    unsubscribe,
)
from pyama.types import MicroscopyMetadata
from pyama.types.tasks import TaskStatus


def _wait_for_terminal_snapshot(task_id: str, *, timeout_s: float = 10.0):
    queue = subscribe(task_id)
    deadline = time() + timeout_s
    try:
        while time() < deadline:
            try:
                snapshot = queue.get(timeout=max(deadline - time(), 0.05))
            except Empty as exc:  # pragma: no cover - defensive timeout guard
                raise AssertionError(f"Timed out waiting for task {task_id}") from exc
            if snapshot.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return snapshot
    finally:
        unsubscribe(task_id, queue)
    raise AssertionError(f"Task {task_id} did not reach a terminal state")


def test_rpc_backend_round_trips_async_model_fit_task(tmp_path: Path) -> None:
    csv_path = tmp_path / "analysis.csv"
    pd.DataFrame.from_records(
        [
            {"frame": 0, "position": 0, "roi": 0, "value": 0.0},
            {"frame": 1, "position": 0, "roi": 0, "value": 0.2},
            {"frame": 2, "position": 0, "roi": 0, "value": 1.0},
            {"frame": 3, "position": 0, "roi": 0, "value": 1.0},
        ]
    ).to_csv(csv_path, index=False)

    start_rpc_backend(cwd=Path.cwd())
    try:
        record = submit_model_fit(
            ModelFitTaskRequest(
                csv_file=csv_path,
                model_type="base",
                frame_interval_minutes=5.0,
            )
        )
        snapshot = _wait_for_terminal_snapshot(record.id)

        assert snapshot.status == TaskStatus.COMPLETED
        results_df, saved_csv_path = snapshot.result
        assert results_df is not None
        assert list(results_df["position"]) == [0]
        assert saved_csv_path == csv_path.with_name("analysis_fitted_base.csv")
        assert saved_csv_path.exists()

        current = get_task(record.id)
        assert current is not None
        assert current.status == TaskStatus.COMPLETED
        assert any(task.id == record.id for task in list_tasks())
    finally:
        shutdown_backend()


def test_rpc_codec_round_trips_microscopy_metadata_with_z_slices() -> None:
    metadata = MicroscopyMetadata(
        file_path=Path("sample.nd2"),
        base_name="sample",
        file_type="nd2",
        height=4,
        width=5,
        n_frames=3,
        channel_names=("PC", "GFP"),
        dtype="uint16",
        timepoints=(0.0, 5.0, 10.0),
        position_list=(0, 1),
        z_slices=(0, 1, 2),
    )

    decoded = from_wire(to_wire(metadata))

    assert decoded == metadata
    assert decoded.n_z == 3


def test_rpc_server_no_longer_exposes_sync_ops() -> None:
    client = PyamaRpcClient(cwd=Path.cwd())
    try:
        with pytest.raises(RuntimeError, match="Unknown RPC method"):
            client.request("ops.list_models", {})
    finally:
        client.close()
