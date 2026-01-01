"""Dummy task implementations for testing."""

import asyncio
from typing import Any

from .base import BaseTask


class DummyTask(BaseTask):
    """
    Dummy task that simulates a long-running process.

    Parameters:
        duration: Total duration in seconds (default: 5)
        steps: Number of progress steps (default: 5)
    """

    async def execute(self) -> dict[str, Any]:
        """Execute the dummy task."""
        # Get parameters with defaults
        duration = self.parameters.get("duration", 5)
        steps = self.parameters.get("steps", 5)

        sleep_time = duration / steps

        for step in range(steps):
            # Check for cancellation
            await self.check_cancelled()

            progress = ((step + 1) / steps) * 100
            message = f"Processing step {step + 1}/{steps}"

            await self.update_progress(progress, message)
            await asyncio.sleep(sleep_time)

        return {
            "message": "Dummy task completed",
            "steps_completed": steps,
            "duration": duration,
        }
