"""FastAPI server for PyAMA Core API."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyama_core.api.routes.data import microscopy_router
from pyama_core.api.routes.processing import config_router, tasks_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="PyAMA Core API",
        description="API for PyAMA microscopy image processing pipeline",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS for local development with Tauri
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",  # Tauri dev server
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:1420",
            "http://127.0.0.1:5173",
            "tauri://localhost",  # Tauri production
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount routers
    app.include_router(microscopy_router, prefix="/data")
    app.include_router(config_router, prefix="/processing")
    app.include_router(tasks_router, prefix="/processing")

    @app.get("/")
    async def root() -> dict:
        """Root endpoint with API info."""
        return {
            "name": "PyAMA Core API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint."""
        return {"status": "healthy"}

    logger.info("PyAMA Core API initialized")
    return app
