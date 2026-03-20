from __future__ import annotations

from pathlib import Path
from queue import Empty
from time import sleep, time

import numpy as np

import pyama.tasks.manager as task_manager_module
from pyama.tasks import CachedStack
from pyama.tasks.manager import TaskManager
from pyama.types import (
    ChannelSelection,
    Channels,
    MicroscopyMetadata,
    ProcessingContext,
    ProcessingParams,
)
from pyama.types.tasks import (
    ProcessingTaskRequest,
    StatisticsTaskRequest,
    TaskStatus,
    VisualizationTaskRequest,
)


def _collect_snapshots(
    manager: TaskManager,
    task_id: str,
    *,
    timeout_s: float = 2.0,
):
    queue = manager.subscribe(task_id)
    snapshots = []
    deadline = time() + timeout_s
    try:
        while time() < deadline:
            try:
                snapshot = queue.get(timeout=max(deadline - time(), 0.01))
            except Empty as exc:  # pragma: no cover - defensive timeout guard
                raise AssertionError(f"Timed out waiting for task {task_id}") from exc
            snapshots.append(snapshot)
            if snapshot.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                return snapshots
    finally:
        manager.unsubscribe(task_id, queue)
    raise AssertionError(f"Task {task_id} did not reach a terminal state")


def test_subscribe_returns_current_snapshot_for_completed_tasks(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "source.npy"
    cached_path = tmp_path / "cached.npy"
    np.save(source_path, np.zeros((1, 2, 2), dtype=np.uint8))

    def fake_get_or_build_uint8(*_args, **_kwargs) -> CachedStack:
        return CachedStack(path=cached_path, shape=(1, 2, 2), n_frames=1)

    monkeypatch.setattr(
        task_manager_module,
        "get_or_build_uint8_impl",
        fake_get_or_build_uint8,
    )

    manager = TaskManager()
    record = manager.submit_visualization(
        VisualizationTaskRequest(source_path=source_path, channel_id="0")
    )

    deadline = time() + 1.0
    while time() < deadline:
        snapshot = manager.get_task(record.id)
        if snapshot is not None and snapshot.status == TaskStatus.COMPLETED:
            break
        sleep(0.01)
    else:  # pragma: no cover - defensive timeout guard
        raise AssertionError("Visualization task did not complete in time")

    queue = manager.subscribe(record.id)
    try:
        snapshot = queue.get(timeout=1.0)
    finally:
        manager.unsubscribe(record.id, queue)

    assert snapshot.status == TaskStatus.COMPLETED
    assert snapshot.result.path == cached_path


def test_processing_task_converts_raw_progress_into_overall_progress(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run_complete_workflow(**kwargs) -> bool:
        progress_reporter = kwargs["progress_reporter"]
        sleep(0.05)
        progress_reporter(
            {
                "event": "frame",
                "step": "copy",
                "fov": 0,
                "channel": 0,
                "t": 4,
                "T": 10,
                "message": "Copying",
                "worker_id": -1,
            }
        )
        sleep(0.05)
        progress_reporter(
            {
                "event": "frame",
                "step": "tracking",
                "fov": 0,
                "t": 9,
                "T": 10,
                "message": "Tracking",
                "worker_id": 0,
            }
        )
        return True

    monkeypatch.setattr(
        task_manager_module,
        "run_complete_workflow",
        fake_run_complete_workflow,
    )

    manager = TaskManager()
    request = ProcessingTaskRequest(
        metadata=MicroscopyMetadata(
            file_path=tmp_path / "fake.nd2",
            base_name="fake",
            file_type="nd2",
            height=1,
            width=1,
            n_frames=10,
            channel_names=("PC",),
            dtype="uint16",
            timepoints=tuple(float(index) for index in range(10)),
            fov_list=(0,),
        ),
        context=ProcessingContext(
            output_dir=tmp_path,
            channels=Channels(
                pc=ChannelSelection(channel=0, features=["area"]),
                fl=[],
            ),
            params=ProcessingParams(),
        ),
        fov_start=0,
        fov_end=0,
        n_workers=1,
    )
    record = manager.submit_processing(request)
    snapshots = _collect_snapshots(manager, record.id)

    progress_states = [snapshot.progress for snapshot in snapshots if snapshot.progress]
    copy_progress = next(
        progress for progress in progress_states if progress.step == "copy"
    )
    tracking_progress = next(
        progress for progress in progress_states if progress.step == "tracking"
    )

    assert copy_progress.percent == 12
    assert copy_progress.details["overall_total"] == 40
    assert copy_progress.details["step_current"] == 5
    assert tracking_progress.percent == 37
    assert tracking_progress.details["overall_current"] == 15
    assert snapshots[-1].status == TaskStatus.COMPLETED


def test_statistics_task_publishes_progress_updates(monkeypatch) -> None:
    expected_result = ("results_df", {"sample": "trace"}, Path("out.csv"))

    def fake_run_folder_statistics(*_args, **kwargs):
        progress_reporter = kwargs["progress_reporter"]
        sleep(0.05)
        progress_reporter(
            {
                "step": "statistics",
                "current": 1,
                "total": 2,
                "progress": 50,
                "message": "Processed sample A",
            }
        )
        sleep(0.05)
        progress_reporter(
            {
                "step": "statistics",
                "current": 2,
                "total": 2,
                "progress": 100,
                "message": "Processed sample B",
            }
        )
        return expected_result

    monkeypatch.setattr(
        task_manager_module,
        "run_folder_statistics_impl",
        fake_run_folder_statistics,
    )

    manager = TaskManager()
    record = manager.submit_statistics(
        StatisticsTaskRequest(mode="auc", folder_path=Path.cwd())
    )
    snapshots = _collect_snapshots(manager, record.id)

    progress_states = [snapshot.progress for snapshot in snapshots if snapshot.progress]
    assert any(progress.percent == 50 for progress in progress_states)
    assert any(progress.percent == 100 for progress in progress_states)
    assert snapshots[-1].result == expected_result


def test_snapshots_are_immutable_replacements(monkeypatch) -> None:
    expected_result = ("results_df", {"sample": "trace"}, Path("out.csv"))

    def fake_run_folder_statistics(*_args, **kwargs):
        progress_reporter = kwargs["progress_reporter"]
        progress_reporter(
            {
                "step": "statistics",
                "current": 1,
                "total": 1,
                "progress": 100,
                "message": "Done",
            }
        )
        return expected_result

    monkeypatch.setattr(
        task_manager_module,
        "run_folder_statistics_impl",
        fake_run_folder_statistics,
    )

    manager = TaskManager()
    record = manager.submit_statistics(
        StatisticsTaskRequest(mode="auc", folder_path=Path.cwd())
    )

    snapshots = _collect_snapshots(manager, record.id)
    terminal_snapshot = snapshots[-1]

    assert record.status == TaskStatus.PENDING
    assert terminal_snapshot.status == TaskStatus.COMPLETED
    assert record is not terminal_snapshot
