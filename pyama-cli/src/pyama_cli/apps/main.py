"""Root CLI assembly for pyama-cli."""

import logging

import typer

from . import modeling, processing, statistics, visualization

app = typer.Typer(help="pyama CLI utilities")


@app.callback()
def main() -> None:
    """pyama utility commands."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return None


processing.register_commands(app)
statistics.register_commands(app)
modeling.register_commands(app)
visualization.register_commands(app)
