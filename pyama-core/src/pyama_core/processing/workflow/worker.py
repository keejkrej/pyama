"""
Workflow worker for executing processing workflows.

This module provides a shared worker class that can be used by both CLI and GUI
to execute processing workflows. The worker handles cancellation, error handling,
and result reporting in a consistent way.
"""

import logging
import threading
from pathlib import Path

from pyama_core.types.processing import ProcessingConfig
from pyama_core.types.microscopy import MicroscopyMetadata
from pyama_core.io import ensure_config
from pyama_core.processing.workflow.run import run_complete_workflow

logger = logging.getLogger(__name__)


class WorkflowWorker:
    """Worker for executing processing workflows.

    This worker encapsulates the workflow execution logic and can be used
    by both CLI and GUI applications. It handles cancellation, error handling,
    and provides a consistent interface for workflow execution.

    All workflow parameters (fovs, batch_size, n_workers) are read from config.params.

    Attributes:
        metadata: Microscopy metadata for the input file
        config: Processing config with channel and parameter configuration
        output_dir: Directory to write outputs
        cancel_event: Threading event for cancellation support
    """

    def __init__(
        self,
        *,
        metadata: MicroscopyMetadata,
        config: ProcessingConfig,
        output_dir: Path,
    ) -> None:
        """Initialize the workflow worker.

        Args:
            metadata: Microscopy metadata for the input file
            config: Processing config with channel and parameter configuration
                - params.fovs: FOV selection ("all" or range like "0-5, 7")
                - params.batch_size: Number of FOVs per batch
                - params.n_workers: Number of parallel workers
            output_dir: Directory to write outputs
        """
        self._metadata = metadata
        self._config = ensure_config(config)
        self._output_dir = output_dir
        self._cancel_event = threading.Event()

    def run(self) -> tuple[bool, str]:
        """Execute the processing workflow.

        Runs the complete workflow and returns the result. Handles exceptions
        and cancellation gracefully.

        Returns:
            Tuple of (success: bool, message: str) indicating workflow result.
        """
        try:
            # Check for cancellation before starting
            if self._cancel_event.is_set():
                logger.info("Workflow cancelled before execution")
                return (False, "Workflow cancelled")

            logger.info(
                "Workflow execution started (fovs=%s, batch_size=%d, workers=%d, output_dir=%s)",
                self._config.params.fovs,
                self._config.params.batch_size,
                self._config.params.n_workers,
                self._output_dir,
            )

            success = run_complete_workflow(
                self._metadata,
                self._config,
                self._output_dir,
                cancel_event=self._cancel_event,
            )

            # Check for cancellation after workflow completion
            if self._cancel_event.is_set():
                logger.info("Workflow was cancelled during execution")
                return (False, "Workflow cancelled")

            if success:
                message = f"Results saved to {self._output_dir}"
                return (True, message)
            else:
                return (False, "Workflow reported failure")

        except Exception as exc:
            logger.exception("Workflow execution failed")
            return (False, f"Workflow error: {exc}")

    def cancel(self) -> None:
        """Cancel the workflow execution.

        Sets the cancellation event that will be checked by the
        underlying workflow implementation to allow for graceful
        termination of processing.
        """
        logger.info(
            "Cancelling workflow execution (output_dir=%s)",
            self._output_dir,
        )
        self._cancel_event.set()

    @property
    def cancel_event(self) -> threading.Event:
        """Get the cancellation event for external monitoring."""
        return self._cancel_event
