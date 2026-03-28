"""Function-based service entrypoints for processing."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Empty, Queue
import logging
import threading
from typing import Callable

from pyama.apps.processing.bbox import load_bbox_rows
from pyama.apps.processing.background import run_background_to_rois_zarr
from pyama.apps.processing.extract import run_extract_to_csv
from pyama.apps.processing.roi import run_roi_to_rois_zarr
from pyama.io import load_microscopy_file
from pyama.io.config import ensure_config
from pyama.types.io import MicroscopyMetadata
from pyama.types.processing import ProcessingConfig
from pyama.types.tasks import ProgressPayload
from pyama.utils.progress import emit_progress
from pyama.utils.processing import resolve_processing_positions

logger = logging.getLogger(__name__)

_STAGE_TO_PROGRESS_STEP = {
    "background": "background_estimation",
    "roi": "roi",
    "extract": "extraction",
}


def _run_position_pipeline(
    *,
    reader,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    position_idx: int,
    worker_id: int,
    cancel_event: threading.Event | None,
    progress_callback: Callable[[dict[str, int | str]], None] | None,
    position_lookup: dict[int, int],
    position_total: int,
) -> bool:
    roi_summary = run_roi_to_rois_zarr(
        reader=reader,
        metadata=metadata,
        config=config,
        output_dir=output_dir,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
        positions_subset=[position_idx],
        worker_id=worker_id,
        global_position_lookup=position_lookup,
        global_position_total=position_total,
    )
    if bool(roi_summary.get("roi_cancelled", False)):
        return True

    background_summary = run_background_to_rois_zarr(
        reader=reader,
        metadata=metadata,
        config=config,
        output_dir=output_dir,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
        positions_subset=[position_idx],
        worker_id=worker_id,
        global_position_lookup=position_lookup,
        global_position_total=position_total,
    )
    if bool(background_summary.get("background_cancelled", False)):
        return True

    extract_summary = run_extract_to_csv(
        metadata=metadata,
        config=config,
        output_dir=output_dir,
        cancel_event=cancel_event,
        progress_callback=progress_callback,
        positions_subset=[position_idx],
        worker_id=worker_id,
        global_position_lookup=position_lookup,
        global_position_total=position_total,
    )
    if bool(extract_summary.get("extract_cancelled", False)):
        return True

    return False


def _run_orchestrator(
    *,
    reader,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
) -> None:
    if cancel_event and cancel_event.is_set():
        return

    config = ensure_config(config)
    resolved_positions = resolve_processing_positions(metadata, config)

    if not resolved_positions:
        return

    worker_count = max(1, min(config.params.n_workers, len(resolved_positions)))
    position_lookup = {
        position_idx: idx + 1 for idx, position_idx in enumerate(resolved_positions)
    }
    position_queue: Queue[int] = Queue()
    for position_idx in resolved_positions:
        position_queue.put(position_idx)

    def run_worker(worker_id: int) -> None:
        while True:
            if cancel_event and cancel_event.is_set():
                break
            try:
                position_idx = position_queue.get_nowait()
            except Empty:
                break

            should_stop = _run_position_pipeline(
                reader=reader,
                metadata=metadata,
                config=config,
                output_dir=output_dir,
                position_idx=position_idx,
                worker_id=worker_id,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                position_lookup=position_lookup,
                position_total=len(resolved_positions),
            )
            if should_stop:
                break

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        list(executor.map(run_worker, range(worker_count)))


def _validate_bbox_inputs(
    *,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
) -> None:
    resolved_positions = resolve_processing_positions(metadata, config)
    for position_idx in resolved_positions:
        position_id = metadata.position_list[position_idx]
        load_bbox_rows(
            output_dir=output_dir,
            position_id=position_id,
            frame_width=metadata.width,
            frame_height=metadata.height,
        )


def run_complete_workflow(
    *,
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: threading.Event | None = None,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
    progress_reporter: Callable[[ProgressPayload], None] | None = None,
) -> bool:
    config = ensure_config(config)

    def _event_to_progress_payload(event: dict[str, int | str]) -> None:
        stage = str(event.get("stage", "processing"))
        step = _STAGE_TO_PROGRESS_STEP.get(stage, stage)
        position_index = int(event.get("position_id", -1))
        channel_id = int(event.get("channel_id", -1))
        frame_index = int(event.get("frame_index", 0))
        frame_total = int(event.get("frame_total", 0))
        worker_id = int(event.get("worker_id", -1))
        message = str(event.get("message", ""))
        emit_progress(
            progress_reporter,
            step=step,
            event="frame",
            position=position_index,
            channel=channel_id if channel_id >= 0 else None,
            current=max(frame_index - 1, 0),
            total=frame_total if frame_total > 0 else None,
            current_key="t",
            total_key="T",
            message=message,
            worker_id=worker_id,
            position_id=position_index,
            stage=stage,
            position_index=event.get("position_index"),
            position_total=event.get("position_total"),
            frame_index=frame_index,
            frame_total=frame_total,
        )

    progress_sink = progress_callback
    if progress_reporter is not None:
        if progress_sink is None:
            progress_sink = _event_to_progress_payload
        else:
            original_sink = progress_sink

            def _combined_progress_sink(event: dict[str, int | str]) -> None:
                original_sink(event)
                _event_to_progress_payload(event)

            progress_sink = _combined_progress_sink

    _validate_bbox_inputs(
        metadata=metadata,
        config=config,
        output_dir=output_dir,
    )

    reader, _loaded_metadata = load_microscopy_file(Path(metadata.file_path))
    try:
        _run_orchestrator(
            reader=reader,
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            cancel_event=cancel_event,
            progress_callback=progress_sink,
        )
    finally:
        try:
            reader.close()
        except Exception:
            logger.debug(
                "Failed to close microscopy reader for %s",
                metadata.file_path,
                exc_info=True,
            )
    return not bool(cancel_event and cancel_event.is_set())


__all__ = [
    "run_complete_workflow",
]
