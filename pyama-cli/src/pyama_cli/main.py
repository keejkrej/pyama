"""Thin CLI entrypoint for pyama-cli."""

from pyama_cli.apps import app

__all__ = ["app"]


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    app()
