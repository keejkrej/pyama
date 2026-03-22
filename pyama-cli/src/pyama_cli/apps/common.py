"""Shared interactive helpers for pyama-cli command modules."""

import logging
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import typer

from pyama.apps.processing.extract import list_fluorescence_features, list_phase_features
from pyama.apps.processing.merge import parse_positions_field
from pyama.io.microscopy import load_microscopy_file

PC_FEATURE_OPTIONS: list[str] = []
FL_FEATURE_OPTIONS: list[str] = []


def configure_logging() -> None:
    """Configure CLI logging once for interactive commands."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def initialize_feature_options() -> tuple[list[str], list[str]]:
    """Load feature options from the core processing package."""
    global PC_FEATURE_OPTIONS, FL_FEATURE_OPTIONS

    try:
        PC_FEATURE_OPTIONS = list_phase_features()
        FL_FEATURE_OPTIONS = list_fluorescence_features()

        if not PC_FEATURE_OPTIONS:
            typer.secho(
                "Warning: No phase contrast features found. Using default 'area' feature.",
                fg=typer.colors.YELLOW,
            )
            PC_FEATURE_OPTIONS = ["area"]

        if not FL_FEATURE_OPTIONS:
            typer.secho(
                "Warning: No fluorescence features found. Using default 'intensity' feature.",
                fg=typer.colors.YELLOW,
            )
            FL_FEATURE_OPTIONS = ["intensity"]

    except Exception as exc:
        typer.secho(
            f"Warning: Failed to discover features dynamically: {exc}. Using defaults.",
            fg=typer.colors.YELLOW,
        )
        PC_FEATURE_OPTIONS = ["area"]
        FL_FEATURE_OPTIONS = ["intensity"]

    return PC_FEATURE_OPTIONS, FL_FEATURE_OPTIONS


def prompt_microscopy_path() -> Path:
    """Prompt until the user provides an existing microscopy file path."""
    while True:
        raw_path = typer.prompt("Enter the path to your microscopy file").strip()
        if not raw_path:
            typer.secho(
                "Please provide a non-empty path.", err=True, fg=typer.colors.RED
            )
            continue
        microscopy_path = Path(raw_path).expanduser()
        if not microscopy_path.exists():
            typer.secho(
                f"Path '{microscopy_path}' does not exist.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        if not microscopy_path.is_file():
            typer.secho(
                f"Path '{microscopy_path}' is not a file.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return microscopy_path


def prompt_channel(prompt_text: str, valid_indices: Iterable[int]) -> int:
    """Prompt for a valid channel index."""
    valid_set = set(valid_indices)
    while True:
        value = typer.prompt(prompt_text).strip()
        try:
            selection = int(value)
        except ValueError:
            typer.secho(
                "Please enter a numeric channel index.", err=True, fg=typer.colors.RED
            )
            continue
        if selection not in valid_set:
            typer.secho(
                f"Channel {selection} is not in the available list: {sorted(valid_set)}",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return selection


def prompt_features(channel_label: str, options: list[str]) -> list[str]:
    """Prompt for enabled features for a channel."""
    selected: list[str] = []
    for feature in options:
        if typer.confirm(f"Enable '{feature}' for {channel_label}?", default=True):
            selected.append(feature)
    return selected


def print_channel_summary(channel_names: list[str]) -> None:
    """Print discovered channels in a numbered list."""
    typer.echo("")
    typer.secho("Discovered channels:", bold=True)
    for idx, name in enumerate(channel_names):
        label = name if name else f"C{idx}"
        typer.echo(f"  [{idx}] {label}")
    typer.echo("")


def prompt_positions_for_sample(sample_name: str) -> str:
    """Prompt for a valid position specification."""
    while True:
        positions_input = typer.prompt(
            f"Positions for '{sample_name}' (e.g., 0:3,5,8:10)"
        ).strip()
        if not positions_input:
            typer.secho(
                "A position specification is required.", err=True, fg=typer.colors.RED
            )
            continue
        try:
            parse_positions_field(positions_input)
        except ValueError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            continue
        return positions_input


def collect_samples_interactively() -> list[dict[str, str]]:
    """Collect sample definitions from the user."""
    samples: list[dict[str, str]] = []
    typer.echo("Configure your samples. Leave the name blank to finish.")
    while True:
        sample_name = typer.prompt("Sample name", default="").strip()
        if not sample_name:
            if samples:
                break
            typer.secho(
                "At least one sample is required.", err=True, fg=typer.colors.RED
            )
            continue
        if any(existing["name"] == sample_name for existing in samples):
            typer.secho(
                f"Sample '{sample_name}' already exists. Choose a different name.",
                err=True,
                fg=typer.colors.RED,
            )
            continue

        positions_text = prompt_positions_for_sample(sample_name)
        samples.append({"name": sample_name, "positions": positions_text})
    return samples


def prompt_path(prompt_text: str, default: Path | None = None) -> Path:
    """Prompt for a filesystem path."""
    while True:
        if default is not None:
            raw_value = typer.prompt(prompt_text, default=str(default)).strip()
        else:
            raw_value = typer.prompt(prompt_text).strip()
        if not raw_value:
            typer.secho("Please provide a path.", err=True, fg=typer.colors.RED)
            continue
        return Path(raw_value).expanduser()


def prompt_existing_file(prompt_text: str, default: Path | None = None) -> Path:
    """Prompt for a file path that must exist."""
    while True:
        path = prompt_path(prompt_text, default=default)
        if not path.exists():
            typer.secho(f"File '{path}' does not exist.", err=True, fg=typer.colors.RED)
            continue
        if not path.is_file():
            typer.secho(f"Path '{path}' is not a file.", err=True, fg=typer.colors.RED)
            continue
        return path


def prompt_directory(
    prompt_text: str,
    default: Path | None = None,
    *,
    must_exist: bool = True,
) -> Path:
    """Prompt for a directory path, optionally creating it."""
    while True:
        path = prompt_path(prompt_text, default=default)
        if path.exists():
            if path.is_dir():
                return path
            typer.secho(
                f"Path '{path}' is not a directory.", err=True, fg=typer.colors.RED
            )
            continue
        if must_exist:
            typer.secho(
                f"Directory '{path}' does not exist.", err=True, fg=typer.colors.RED
            )
            continue
        path.mkdir(parents=True, exist_ok=True)
        return path


def prompt_int(prompt_text: str, default: int, *, minimum: int = 0) -> int:
    """Prompt for an integer constrained by a minimum."""
    while True:
        value = typer.prompt(prompt_text, default=str(default)).strip()
        try:
            number = int(value)
        except ValueError:
            typer.secho(
                "Please enter an integer value.", err=True, fg=typer.colors.RED
            )
            continue
        if number < minimum:
            typer.secho(
                f"Value must be >= {minimum}.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return number


def load_metadata_for_prompt(microscopy_path: Path):
    """Load microscopy metadata and close the reader after inspection."""
    typer.echo("\nLoading microscopy metadata...")
    try:
        image, metadata = load_microscopy_file(microscopy_path)
        if hasattr(image, "close"):
            try:
                image.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
        return metadata
    except Exception as exc:  # pragma: no cover - runtime path
        typer.secho(
            f"Failed to load microscopy file: {exc}", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1) from exc


def create_fluorescence_feature_map() -> defaultdict[int, set[str]]:
    """Return the mutable fluorescence-channel feature map used by the wizard."""
    return defaultdict(set)
