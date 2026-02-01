"""API route modules.

This module provides the aggregated api_router that groups all REST routes
under the /api prefix.
"""

from fastapi import APIRouter

from pyama_core.api.routes.data import microscopy_router
from pyama_core.api.routes.processing import config_router, tasks_router
from pyama_core.api.routes.visualization import visualization_router

# Create aggregated router with /api prefix
api_router = APIRouter(prefix="/api")
api_router.include_router(microscopy_router, prefix="/data")
api_router.include_router(config_router, prefix="/processing")
api_router.include_router(tasks_router, prefix="/processing")
api_router.include_router(visualization_router, prefix="/visualization")

__all__ = [
    "api_router",
    "microscopy_router",
    "config_router",
    "tasks_router",
    "visualization_router",
]
