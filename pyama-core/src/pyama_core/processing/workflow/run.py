"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pyama_core.types.processing import ProcessingConfig
from pyama_core.types.microscopy import MicroscopyMetadata
from pyama_core.io import (
    get_config_path,
    ensure_config,
    save_config,
)
from pyama_core.processing.workflow.services import (
    BackgroundEstimationService,
    CopyingService,
    CroppingService,
    ExtractionService,
    SegmentationService,
    TrackingService,
)

logger = logging.getLogger(__name__)


def _compute_batches(fovs: list[int], batch_size: int) -> list[list[int]]:
    """Split FOV indices into contiguous batches of size ``batch_size``."""
    batches: list[list[int]] = []
    total_fovs = len(fovs)
    for batch_start in range(0, total_fovs, batch_size):
        batch_end = min(batch_start + batch_size, total_fovs)
        batches.append(fovs[batch_start:batch_end])
    return batches


def _split_worker_ranges(fovs: list[int], n_workers: int) -> list[list[int]]:
    """Split FOV indices into up to ``n_workers`` contiguous, evenly sized ranges."""
    if n_workers <= 0:
        return [fovs] if fovs else []
    fovs_per_worker = len(fovs) // n_workers
    remainder = len(fovs) % n_workers
    worker_ranges: list[list[int]] = []
    start_id = 0
    for i in range(n_workers):
        count = fovs_per_worker + (1 if i < remainder else 0)
        if count > 0:
            end_id = start_id + count
            worker_ranges.append(fovs[start_id:end_id])
            start_id = end_id
    return worker_ranges


def run_single_worker(
    fovs: list[int],
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: threading.Event | None = None,
) -> tuple[list[int], int, int, str]:
    """Process a contiguous range of FOV indices through all pipeline steps.

    Returns a tuple of (fovs, successful_count, failed_count, message).
    """
    logger = logging.getLogger(__name__)
    successful_count = 0

    try:
        config = ensure_config(config)

        # Read algorithm choice from config params
        seg_method = config.params.segmentation_method
        track_method = config.params.tracking_method

        segmentation = SegmentationService(method=seg_method)
        tracking = TrackingService(method=track_method)
        background_estimation = BackgroundEstimationService()
        cropping = CroppingService()
        trace_extraction = ExtractionService()

        logger.info("Processing FOVs %d-%d", fovs[0], fovs[-1])

        # Check for cancellation before starting processing
        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled before processing"
            )
            return (fovs, 0, len(fovs), "Cancelled before processing")

        logger.info("Starting Segmentation for FOVs %d-%d", fovs[0], fovs[-1])
        segmentation.process_all_fovs(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after segmentation"
            )
            return (fovs, 1, len(fovs) - 1, "Cancelled after segmentation")

        logger.info("Starting Tracking for FOVs %d-%d", fovs[0], fovs[-1])
        tracking.process_all_fovs(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after tracking"
            )
            return (fovs, 2, len(fovs) - 2, "Cancelled after tracking")

        logger.info("Starting Background Estimation for FOVs %d-%d", fovs[0], fovs[-1])
        background_estimation.process_all_fovs(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after background estimation"
            )
            return (fovs, 3, len(fovs) - 3, "Cancelled after background estimation")

        logger.info("Starting Cropping for FOVs %d-%d", fovs[0], fovs[-1])
        cropping.process_all_fovs(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )

        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Worker for FOVs {fovs[0]}-{fovs[-1]} cancelled after cropping"
            )
            return (fovs, 4, len(fovs) - 4, "Cancelled after cropping")

        logger.info("Starting Extraction for FOVs %d-%d", fovs[0], fovs[-1])
        trace_extraction.process_all_fovs(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
            fov_start=fovs[0],
            fov_end=fovs[-1],
            cancel_event=cancel_event,
        )

        successful_count = len(fovs)
        success_msg = f"Completed processing FOVs {fovs[0]}-{fovs[-1]}"
        logger.info("Completed processing FOVs %d-%d", fovs[0], fovs[-1])
        return fovs, successful_count, 0, success_msg

    except Exception as e:
        logger.exception("Error processing FOVs %d-%d", fovs[0], fovs[-1])
        error_msg = f"Error processing FOVs {fovs[0]}-{fovs[-1]}: {str(e)}"
        return fovs, 0, len(fovs), error_msg


def run_complete_workflow(
    metadata: MicroscopyMetadata,
    config: ProcessingConfig,
    output_dir: Path,
    cancel_event: threading.Event | None = None,
) -> bool:
    """Run the complete processing workflow.

    The workflow consists of these steps (parallelized unless noted):

    1. Copying (sequential per batch): Extract data from ND2 files
    2. Segmentation: Cell detection (requires PC channel)
    3. Tracking: Cell tracking across frames (requires PC channel)
    4. Background Estimation: Fluorescence background fitting (requires FL channels)
    5. Cropping: Extract cell bounding boxes (works with PC-only, optionally with FL)
    6. Extraction: Feature extraction to CSV (position/bbox with PC-only, more features with FL)

    **Channel-Conditional Behavior:**
    - No PC channel configured: Segmentation, tracking, cropping, extraction are skipped
    - No FL channels configured: Background estimation is skipped automatically
    - PC channel with no features: Extraction still outputs position/bbox data for tracking

    Args:
        metadata: Microscopy file metadata.
        config: Processing configuration (channels and params).
            - params.fovs: FOV selection ("all" or range like "0-5, 7")
            - params.batch_size: Number of FOVs per batch
            - params.n_workers: Number of parallel workers
        output_dir: Directory to write outputs.
        cancel_event: Optional event to signal cancellation.

    Returns:
        True if all FOVs processed successfully, False otherwise.
    """
    from pyama_core.processing.merge.run import parse_fov_range

    config = ensure_config(config)
    overall_success = False

    copy_service = CopyingService()

    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Resolve FOVs from config
        fovs = config.params.fovs
        n_fovs = metadata.n_fovs
        if not fovs or fovs.lower() == "all":
            fov_indices = list(range(n_fovs))
        else:
            fov_indices = parse_fov_range(fovs)
            invalid = [f for f in fov_indices if f < 0 or f >= n_fovs]
            if invalid:
                raise ValueError(f"Invalid FOV indices: {invalid} (valid: 0-{n_fovs - 1})")
        batch_size = config.params.batch_size
        n_workers = config.params.n_workers

        total_fovs = len(fov_indices)

        completed_fovs = 0

        batches = _compute_batches(fov_indices, batch_size)
        precomputed_worker_ranges = [
            _split_worker_ranges(batch_fovs, n_workers) for batch_fovs in batches
        ]

        for batch_id, batch_fovs in enumerate(batches):
            # Check for cancellation before starting batch
            if cancel_event and cancel_event.is_set():
                logger.info("Workflow cancelled before batch processing")
                return False

            logger.info("Extracting batch: FOVs %d-%d", batch_fovs[0], batch_fovs[-1])
            try:
                copy_service.process_all_fovs(
                    metadata=metadata,
                    config=config,
                    output_dir=output_dir,
                    fov_start=batch_fovs[0],
                    fov_end=batch_fovs[-1],
                    cancel_event=cancel_event,
                )
            except Exception as e:
                logger.error(
                    "Failed to extract batch starting at FOV %d: %s",
                    batch_fovs[0],
                    e,
                )
                return False

            # Check for cancellation after copying
            if cancel_event and cancel_event.is_set():
                logger.info(
                    "Workflow cancelled after copying, before parallel processing"
                )
                return False

            logger.info("Processing batch in parallel with %d workers", n_workers)

            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                worker_ranges = precomputed_worker_ranges[batch_id]

                futures = {
                    executor.submit(
                        run_single_worker,
                        fov_range,
                        metadata,
                        config,
                        output_dir,
                        cancel_event,
                    ): fov_range
                    for fov_range in worker_ranges
                    if fov_range
                }

                for future in as_completed(futures):
                    # Check for cancellation after each future completes
                    if cancel_event and cancel_event.is_set():
                        logger.info("Workflow cancelled during parallel processing")
                        for remaining_future in futures:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        return False

                    fov_range = futures[future]
                    try:
                        fov_indices_res, successful, failed, message = future.result()
                        completed_fovs += successful
                        if failed > 0:
                            logger.error(
                                "%d FOVs failed in range %d-%d: %s",
                                failed,
                                fov_indices_res[0],
                                fov_indices_res[-1],
                                message,
                            )
                    except Exception as e:
                        error_msg = f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {str(e)}"
                        logger.error(error_msg)

                    progress = int(completed_fovs / total_fovs * 100)
                    logger.info("Progress: %d%%", progress)

        # Final cancellation check after all batches
        if cancel_event and cancel_event.is_set():
            logger.info("Workflow cancelled after batch processing")
            return False

        overall_success = completed_fovs == total_fovs
        logger.info("Completed processing %d/%d FOVs", completed_fovs, total_fovs)

        # Save config to output directory for reference
        # Skip if config already exists (e.g., saved by CLI before workflow execution)
        config_file = get_config_path(output_dir)
        if not config_file.exists():
            try:
                save_config(config, config_file)
            except Exception as e:
                logger.warning("Failed to save processing_config.yaml: %s", e)
        else:
            logger.debug("Config file already exists at %s, skipping save", config_file)

        return overall_success
    except Exception as e:
        error_msg = f"Error in workflow pipeline: {str(e)}"
        logger.exception(error_msg)
        return False


__all__ = [
    "run_complete_workflow",
]
