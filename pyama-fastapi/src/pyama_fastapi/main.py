"""Main FastAPI application for PyAMA chat."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting pyama-fastapi server")
    yield
    logger.info("Shutting down pyama-fastapi server")


app = FastAPI(
    title="PyAMA FastAPI",
    description="Chat backend for PyAMA microscopy analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "pyama-fastapi"}


@app.post("/chat")
async def chat(message: str) -> dict[str, str]:
    """Simple chat endpoint."""
    # TODO: Integrate with pyama-core and LLM
    return {"response": f"You said: {message}"}


def run() -> None:
    """Run the FastAPI server."""
    uvicorn.run(
        "pyama_fastapi.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    run()
