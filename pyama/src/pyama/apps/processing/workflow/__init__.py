"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from pyama.apps.processing.workflow.run import run_complete_workflow
from pyama.types.processing import (
    ProcessingContext,
    ensure_context,
)

__all__ = ["run_complete_workflow", "ProcessingContext", "ensure_context"]
