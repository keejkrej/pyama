"""Processing routes - configuration and task management."""

from pyama_core.api.routes.processing.config import router as config_router
from pyama_core.api.routes.processing.tasks import router as tasks_router

__all__ = ["config_router", "tasks_router"]
