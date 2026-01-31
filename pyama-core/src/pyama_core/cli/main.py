"""Command-line helpers for pyama-core."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import typer
import yaml

from pyama_core.types.processing import ProcessingConfig, ProcessingParams
from pyama_core.io import (
    load_microscopy_file,
    save_config,
    get_config_path,
    load_config,
)
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.processing.merge import (
    parse_fov_range,
)
from pyama_core.processing.merge import (
    run_merge as run_core_merge,
)
from pyama_core.processing.segmentation import list_segmenters
from pyama_core.processing.tracking import list_trackers
from pyama_core.processing.workflow.run import run_complete_workflow
from pyama_core.processing.workflow.worker import WorkflowWorker
from pyama_core.types.processing import Channels
from pyama_core.utils.plotting import plot_numpy_array

app = typer.Typer(help="pyama-core utilities")
logger = logging.getLogger(__name__)


def _format_fov_list(fov_list: list[int]) -> str:
    """Format FOV list for display (compact representation with ranges).

    Examples:
        [0, 1, 2, 5, 7, 8, 9] -> "0-2, 5, 7-9"
        [0] -> "0"
        [] -> "(none)"
    """
    if not fov_list:
        return "(none)"

    sorted_fovs = sorted(set(fov_list))
    if len(sorted_fovs) == 1:
        return str(sorted_fovs[0])

    # Group consecutive FOVs into ranges
    ranges: list[str] = []
    start = sorted_fovs[0]
    end = sorted_fovs[0]

    for fov in sorted_fovs[1:]:
        if fov == end + 1:
            end = fov
        else:
            # Save current range and start new one
            if start == end:
                ranges.append(str(start))
            else:
                ranges.append(f"{start}-{end}")
            start = fov
            end = fov

    # Don't forget the last range
    if start == end:
        ranges.append(str(start))
    else:
        ranges.append(f"{start}-{end}")

    return ", ".join(ranges)


@app.callback()
def main() -> None:
    """pyama-core utility commands."""
    # Configure basic logging so info-level messages are visible by default.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        # Suppress verbose debug messages from fsspec (used by bioio)
        logging.getLogger("fsspec.local").setLevel(logging.WARNING)
    return None


# =============================================================================
# INTERACTIVE CLI COMMANDS
# =============================================================================

# Dynamic feature discovery - will be populated at runtime
PC_FEATURE_OPTIONS: list[str] = []
FL_FEATURE_OPTIONS: list[str] = []


def _prompt_nd2_path() -> Path:
    """Prompt until the user provides an ND2 path that exists."""
    while True:
        raw_path = typer.prompt("Enter the path to your ND2 file").strip()
        if not raw_path:
            typer.secho(
                "Please provide a non-empty path.", err=True, fg=typer.colors.RED
            )
            continue
        nd2_path = Path(raw_path).expanduser()
        if not nd2_path.exists():
            typer.secho(
                f"Path '{nd2_path}' does not exist.", err=True, fg=typer.colors.RED
            )
            continue
        if not nd2_path.is_file():
            typer.secho(
                f"Path '{nd2_path}' is not a file.", err=True, fg=typer.colors.RED
            )
            continue
        return nd2_path


def _prompt_channel(prompt_text: str, valid_indices: Iterable[int]) -> int:
    """Prompt for a channel index until a valid selection is made."""
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


def _prompt_features(channel_label: str, options: list[str]) -> list[str]:
    """Prompt for a set of features given a list of available options."""
    selected: list[str] = []
    for feature in options:
        if typer.confirm(f"Enable '{feature}' for {channel_label}?", default=True):
            selected.append(feature)
    return selected


def _prompt_choice(prompt_text: str, options: list[str], default: str) -> str:
    """Prompt for a choice from a list of options."""
    while True:
        typer.echo(f"\n{prompt_text}")
        for idx, option in enumerate(options, 1):
            marker = " (default)" if option == default else ""
            typer.echo(f"  [{idx}] {option}{marker}")
        value = typer.prompt("Select option", default=default).strip()
        if value in options:
            return value
        # Try numeric selection
        try:
            idx = int(value)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        typer.secho(
            f"Invalid choice '{value}'. Please select from {options}",
            err=True,
            fg=typer.colors.RED,
        )


def _prompt_float(
    prompt_text: str,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Prompt for a float value with optional min/max constraints."""
    while True:
        value = typer.prompt(prompt_text, default=str(default)).strip()
        try:
            number = float(value)
        except ValueError:
            typer.secho("Please enter a numeric value.", err=True, fg=typer.colors.RED)
            continue
        if minimum is not None and number < minimum:
            typer.secho(
                f"Value must be >= {minimum}.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        if maximum is not None and number > maximum:
            typer.secho(
                f"Value must be <= {maximum}.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return number


def _print_channel_summary(channel_names: list[str]) -> None:
    typer.echo("")
    typer.secho("Discovered channels:", bold=True)
    for idx, name in enumerate(channel_names):
        label = name if name else f"C{idx}"
        typer.echo(f"  [{idx}] {label}")
    typer.echo("")


def _prompt_fovs_for_sample(sample_name: str) -> str:
    """Prompt for a valid FOV specification."""
    while True:
        fovs_input = typer.prompt(
            f"FOVs for '{sample_name}' (e.g., 0-5, 7, 9-11)"
        ).strip()
        if not fovs_input:
            typer.secho(
                "A FOV specification is required.", err=True, fg=typer.colors.RED
            )
            continue
        try:
            parse_fov_range(fovs_input)
        except ValueError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            continue
        return fovs_input


def _collect_samples_interactively() -> list[dict[str, str]]:
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

        fovs_text = _prompt_fovs_for_sample(sample_name)
        samples.append({"name": sample_name, "fovs": fovs_text})
    return samples


def _prompt_path(prompt_text: str, default: Path | None = None) -> Path:
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


def _prompt_existing_file(prompt_text: str, default: Path | None = None) -> Path:
    """Prompt for a file path that must exist."""
    while True:
        path = _prompt_path(prompt_text, default=default)
        if not path.exists():
            typer.secho(f"File '{path}' does not exist.", err=True, fg=typer.colors.RED)
            continue
        if not path.is_file():
            typer.secho(f"Path '{path}' is not a file.", err=True, fg=typer.colors.RED)
            continue
        return path


def _prompt_directory(
    prompt_text: str, default: Path | None = None, must_exist: bool = True
) -> Path:
    """Prompt for a directory path, optionally creating it."""
    while True:
        path = _prompt_path(prompt_text, default=default)
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


def _save_samples_yaml(path: Path, samples: list[dict[str, str]]) -> None:
    """Persist the samples list to YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"samples": samples}, handle, sort_keys=False)


@app.command()
def workflow(
    config_path: Path | None = typer.Option(
        None, "--config", "-c", help="Path to processing config YAML file"
    ),
    nd2_path: Path | None = typer.Option(
        None, "--nd2-path", "-n", help="Path to ND2 microscopy file"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory for results"
    ),
) -> None:
    """Run a processing workflow, either interactively or with provided config file.

    If --config is provided, loads configuration from the YAML file and runs non-interactively.
    Otherwise, runs an interactive wizard to collect inputs.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)

    # Initialize feature options dynamically
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
                "Warning: No fluorescence features found. Using default 'intensity_total' feature.",
                fg=typer.colors.YELLOW,
            )
            FL_FEATURE_OPTIONS = ["intensity_total"]

    except Exception as exc:
        typer.secho(
            f"Warning: Failed to discover features dynamically: {exc}. Using defaults.",
            fg=typer.colors.YELLOW,
        )
        PC_FEATURE_OPTIONS = ["area"]
        FL_FEATURE_OPTIONS = ["intensity_total"]

    # Non-interactive mode: load config from file
    if config_path is not None:
        config_path = Path(config_path).expanduser()
        if not config_path.exists():
            typer.secho(
                f"Config file not found: {config_path}", err=True, fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

        typer.echo(f"Loading configuration from {config_path}...")
        try:
            config = load_config(config_path)
        except Exception as exc:
            typer.secho(f"Failed to load config: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc

        # Output directory is required for non-interactive mode
        if output_dir is None:
            typer.secho(
                "Output directory is required when using --config. Use --output-dir to specify it.",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        output_dir = Path(output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        # Get ND2 path (required for non-interactive mode)
        if nd2_path is None:
            typer.secho(
                "ND2 file path is required when using --config. Use --nd2-path to specify it.",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        nd2_path = Path(nd2_path).expanduser()
        if not nd2_path.exists():
            typer.secho(
                f"ND2 file not found: {nd2_path}", err=True, fg=typer.colors.RED
            )
            raise typer.Exit(code=1)

        # Load metadata
        typer.echo(f"Loading microscopy metadata from {nd2_path}...")
        try:
            image, metadata = load_microscopy_file(nd2_path)
            if hasattr(image, "close"):
                try:
                    image.close()
                except Exception:  # pragma: no cover - best effort cleanup
                    pass
        except Exception as exc:
            typer.secho(
                f"Failed to load microscopy file: {exc}", err=True, fg=typer.colors.RED
            )
            raise typer.Exit(code=1) from exc

        # Validate config
        if config.channels is None:
            typer.secho(
                "Config file missing channels configuration",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        # Display configuration summary
        typer.echo("\n" + "=" * 60)
        typer.secho("Processing Configuration", bold=True)
        typer.echo("=" * 60)
        typer.echo(f"\nChannels:")
        typer.echo(f"  Phase Contrast:")
        pc_ch = config.channels.get_pc_channel()
        pc_feats = config.channels.get_pc_features()
        typer.echo(f"    Channel: {pc_ch}")
        typer.echo(
            f"    Features: {', '.join(pc_feats) if pc_feats else '(none)'}"
        )
        if config.channels.fl:
            typer.echo(f"  Fluorescence:")
            for ch, feats in config.channels.fl.items():
                typer.echo(f"    Channel {ch}: {', '.join(feats)}")
        else:
            typer.echo(f"  Fluorescence: (none)")
        typer.echo(f"\nProcessing Parameters:")
        typer.echo(f"  Segmentation method: {config.params.segmentation_method}")
        typer.echo(f"  Tracking method: {config.params.tracking_method}")
        typer.echo(f"  Background weight: {config.params.background_weight}")
        typer.echo(f"\nWorkflow Parameters:")
        typer.echo(f"  FOVs: {config.params.fovs}")
        typer.echo(f"  Batch size: {config.params.batch_size}")
        typer.echo(f"  Number of workers: {config.params.n_workers}")
        typer.echo(f"\nOutput Directory: {output_dir}")
        typer.echo("=" * 60)

        typer.secho("\nStarting workflow...", bold=True)

        # Create and run workflow worker
        worker = WorkflowWorker(
            metadata=metadata,
            config=config,
            output_dir=output_dir,
        )

        try:
            success, message = worker.run()
        except KeyboardInterrupt:
            typer.echo("\n")
            typer.secho("Workflow interrupted by user", fg=typer.colors.YELLOW)
            worker.cancel()
            raise typer.Exit(code=130)  # Standard exit code for SIGINT
        except Exception as exc:  # pragma: no cover - defensive
            typer.secho(f"Workflow failed: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

        status = "SUCCESS" if success else "FAILED"
        color = typer.colors.GREEN if success else typer.colors.RED
        typer.secho(f"Workflow finished: {status}", bold=True, fg=color)
        if message:
            typer.echo(f"  {message}")

        return

    # Interactive mode: prompt for all inputs
    typer.echo(
        "Welcome to PyAMA workflow! Let's collect the inputs for PyAMA processing.\n"
    )
    nd2_path = _prompt_nd2_path()

    typer.echo("\nLoading microscopy metadata...")
    try:
        image, metadata = load_microscopy_file(nd2_path)
        if hasattr(image, "close"):
            try:
                image.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
    except Exception as exc:  # pragma: no cover - runtime path
        typer.secho(
            f"Failed to load microscopy file: {exc}", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1) from exc

    channel_names = metadata.channel_names or [
        f"C{i}" for i in range(metadata.n_channels)
    ]
    _print_channel_summary(channel_names)

    pc_channel = _prompt_channel(
        "Select the phase contrast (PC) channel index",
        range(len(channel_names)),
    )

    typer.echo(f"\nAvailable phase contrast features: {', '.join(PC_FEATURE_OPTIONS)}")
    pc_features = _prompt_features(f"PC channel [{pc_channel}]", PC_FEATURE_OPTIONS)
    typer.echo("")

    fl_feature_map: dict[int, set[str]] = defaultdict(set)

    typer.echo(
        "Configure fluorescence (FL) channels. Leave blank at any prompt to finish."
    )

    while True:
        entry = typer.prompt(
            "Select a fluorescence channel index (blank to finish)",
            default="",
        ).strip()
        if entry == "":
            break
        try:
            fl_channel = int(entry)
        except ValueError:
            typer.secho(
                "Please enter a numeric channel index.", err=True, fg=typer.colors.RED
            )
            continue
        if fl_channel == pc_channel:
            typer.secho(
                "Channel already used for PC. Pick a different channel.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        if fl_channel not in range(len(channel_names)):
            typer.secho(
                f"Channel {fl_channel} is not valid. Available indices: {list(range(len(channel_names)))}",
                err=True,
                fg=typer.colors.RED,
            )
            continue

        typer.echo(f"Available fluorescence features: {', '.join(FL_FEATURE_OPTIONS)}")
        features = _prompt_features(f"FL channel [{fl_channel}]", FL_FEATURE_OPTIONS)
        if not features:
            typer.secho(
                "No features selected for this channel; skipping.",
                err=True,
                fg=typer.colors.YELLOW,
            )
            continue
        fl_feature_map[fl_channel].update(features)
        typer.echo("")

    output_dir_input = typer.prompt(
        "Enter output directory for results",
        default=str(nd2_path.parent),
    ).strip()
    output_dir = Path(output_dir_input).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prompt for processing parameters
    typer.echo("\n" + "=" * 60)
    typer.secho("Processing Parameters", bold=True)
    typer.echo("=" * 60)

    # Segmentation method
    try:
        seg_methods = list_segmenters()
    except Exception:
        seg_methods = ["logstd", "cellpose"]
    seg_method = _prompt_choice(
        "Select segmentation method",
        seg_methods,
        default="logstd",
    )

    # Tracking method
    try:
        track_methods = list_trackers()
    except Exception:
        track_methods = ["iou", "btrack"]
    track_method = _prompt_choice(
        "Select tracking method",
        track_methods,
        default="iou",
    )

    # Background weight
    background_weight = _prompt_float(
        "Background weight (0.0-1.0)",
        default=1.0,
        minimum=0.0,
        maximum=1.0,
    )

    max_fov = metadata.n_fovs - 1
    default_fov_spec = f"0-{max_fov}" if max_fov > 0 else "0"

    def _prompt_fov_list(max_fov: int) -> list[int]:
        """Prompt for flexible FOV specification (e.g., '0-5, 7, 10-15')."""
        while True:
            fov_spec = typer.prompt(
                f"FOVs (e.g., '0-5, 7, 10-15', valid: 0-{max_fov})",
                default=default_fov_spec,
            ).strip()
            try:
                fov_list = parse_fov_range(fov_spec)
            except ValueError as exc:
                typer.secho(f"Invalid FOV format: {exc}", err=True, fg=typer.colors.RED)
                continue
            # Validate FOV indices are in range
            invalid = [f for f in fov_list if f < 0 or f > max_fov]
            if invalid:
                typer.secho(
                    f"FOV indices out of range (valid: 0-{max_fov}): {invalid}",
                    err=True,
                    fg=typer.colors.RED,
                )
                continue
            return fov_list

    def _prompt_int(prompt_text: str, default: int, minimum: int = 0) -> int:
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

    typer.echo("\n" + "=" * 60)
    typer.secho("Workflow Execution Parameters", bold=True)
    typer.echo("=" * 60)

    fov_list = _prompt_fov_list(max_fov)
    batch_size = _prompt_int("Batch size", 1, minimum=1)
    n_workers = _prompt_int("Number of workers", 1, minimum=1)

    # Create ProcessingConfig with all collected parameters
    config = ProcessingConfig(
        channels=Channels(
            pc={pc_channel: sorted(pc_features)},
            fl={
                channel: sorted(features)
                for channel, features in sorted(fl_feature_map.items())
            },
        ),
        params=ProcessingParams(
            segmentation_method=seg_method,
            tracking_method=track_method,
            background_weight=background_weight,
            fov_list=fov_list,
            batch_size=batch_size,
            n_workers=n_workers,
        ),
    )

    # Display complete ProcessingConfig summary
    typer.echo("\n" + "=" * 60)
    typer.secho("Processing Configuration Summary", bold=True)
    typer.echo("=" * 60)
    typer.echo(f"\nChannels:")
    typer.echo(f"  Phase Contrast:")
    typer.echo(f"    Channel: {pc_channel}")
    typer.echo(
        f"    Features: {', '.join(sorted(pc_features)) if pc_features else '(none)'}"
    )
    if fl_feature_map:
        typer.echo(f"  Fluorescence:")
        for ch, features in sorted(fl_feature_map.items()):
            typer.echo(f"    Channel {ch}: {', '.join(sorted(features))}")
    else:
        typer.echo(f"  Fluorescence: (none)")
    typer.echo(f"\nProcessing Parameters:")
    typer.echo(f"  Segmentation method: {seg_method}")
    typer.echo(f"  Tracking method: {track_method}")
    typer.echo(f"  Background weight: {background_weight}")
    typer.echo(f"\nWorkflow Parameters:")
    typer.echo(f"  FOVs: {_format_fov_list(fov_list)}")
    typer.echo(f"  Batch size: {batch_size}")
    typer.echo(f"  Number of workers: {n_workers}")
    typer.echo(f"\nOutput Directory: {output_dir}")
    typer.echo("=" * 60)

    # Ask for confirmation before proceeding
    typer.echo("")
    if not typer.confirm("Proceed with workflow execution?", default=True):
        typer.secho("Workflow cancelled by user.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    # Save config YAML so user can use --config flag later
    config_yaml_path = get_config_path(output_dir)
    save_config(config, config_yaml_path)
    typer.secho(
        f"Saved processing config to {config_yaml_path}",
        fg=typer.colors.GREEN,
    )

    typer.secho("\nStarting workflow...", bold=True)

    # Create and run workflow worker
    worker = WorkflowWorker(
        metadata=metadata,
        config=config,
        output_dir=output_dir,
        fov_list=fov_list,
        batch_size=batch_size,
        n_workers=n_workers,
    )

    try:
        success, message = worker.run()
    except KeyboardInterrupt:
        typer.echo("\n")
        typer.secho("Workflow interrupted by user", fg=typer.colors.YELLOW)
        worker.cancel()
        raise typer.Exit(code=130)  # Standard exit code for SIGINT
    except Exception as exc:  # pragma: no cover - defensive
        typer.secho(f"Workflow failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    status = "SUCCESS" if success else "FAILED"
    color = typer.colors.GREEN if success else typer.colors.RED
    typer.secho(f"Workflow finished: {status}", bold=True, fg=color)
    if message:
        typer.echo(f"  {message}")


@app.command()
def merge() -> None:
    """Run an interactive merge wizard to combine CSV outputs from multiple samples."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)
    typer.echo("Welcome to PyAMA merge! Let's gather the inputs for CSV merging.\n")

    samples = _collect_samples_interactively()
    typer.echo("")

    default_sample_yaml = Path.cwd() / "samples.yaml"
    sample_yaml_path = _prompt_path(
        "Enter the path to save samples.yaml",
        default=default_sample_yaml,
    )
    _save_samples_yaml(sample_yaml_path, samples)
    typer.secho(
        f"Saved {len(samples)} sample(s) to {sample_yaml_path}",
        fg=typer.colors.GREEN,
    )
    typer.echo("")

    default_input = sample_yaml_path.parent
    input_dir = _prompt_directory(
        "Enter the input directory containing processed FOV folders",
        default=default_input,
        must_exist=True,
    )

    output_folder_default = sample_yaml_path.parent / "merge_output"
    output_folder = _prompt_directory(
        "Enter the output directory for merged CSV files",
        default=output_folder_default,
        must_exist=False,
    )

    typer.echo("")
    typer.secho("Starting merge...", bold=True)

    try:
        message = run_core_merge(
            sample_yaml=sample_yaml_path,
            output_dir=output_folder,
            input_dir=input_dir,
        )
    except Exception as exc:  # pragma: no cover - runtime path
        typer.secho(f"Merge failed: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.secho(message, fg=typer.colors.GREEN, bold=True)


@app.command()
def trajectory(
    csv_path: Path = typer.Argument(..., help="Path to traces CSV file"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for plot (default: <csv_path>_trajectories.png)",
    ),
    good_only: bool = typer.Option(
        True, "--good-only/--all", help="Only plot trajectories with good=True"
    ),
    alpha: float = typer.Option(
        0.6, "--alpha", help="Transparency of trajectory lines (0-1)"
    ),
) -> None:
    """Plot cell trajectories from a traces CSV file."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    csv_path = csv_path.expanduser()
    if not csv_path.exists():
        typer.secho(
            f"CSV file '{csv_path}' does not exist.", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1)

    if not csv_path.is_file():
        typer.secho(f"Path '{csv_path}' is not a file.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(f"Loading trajectory data from {csv_path}...")
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as exc:
        typer.secho(
            f"Missing required dependencies: {exc}. Install with: pip install pandas matplotlib numpy",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1) from exc

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        typer.secho(f"Failed to read CSV file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    # Validate required columns
    required_cols = {"fov", "cell", "frame", "xc", "yc"}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        typer.secho(
            f"CSV file missing required columns: {missing_cols}",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    # Filter by good flag if requested
    if good_only and "good" in df.columns:
        df = df[df["good"] == True]  # noqa: E712
        typer.echo(f"Filtered to {len(df)} rows with good=True")

    # Group by (fov, cell) to get trajectories
    grouped = df.groupby(["fov", "cell"])
    n_trajectories = len(grouped)
    typer.echo(f"Found {n_trajectories} cell trajectories")

    if n_trajectories == 0:
        typer.secho("No trajectories to plot.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 10))

    # Use a colormap to distinguish trajectories
    colors = plt.cm.tab20(np.linspace(0, 1, min(n_trajectories, 20)))
    if n_trajectories > 20:
        # Cycle through colors if we have more than 20 trajectories
        colors = plt.cm.tab20(np.linspace(0, 1, 20))
        color_cycle = np.tile(colors, (n_trajectories // 20 + 1, 1))
        colors = color_cycle[:n_trajectories]

    for idx, ((fov, cell), group) in enumerate(grouped):
        # Sort by frame to ensure correct trajectory order
        group_sorted = group.sort_values("frame")

        # Get xc, yc coordinates
        x_coords = group_sorted["xc"].values
        y_coords = group_sorted["yc"].values

        # Plot trajectory line
        ax.plot(
            x_coords,
            y_coords,
            color=colors[idx % len(colors)],
            alpha=alpha,
            linewidth=1.5,
            label=f"FOV {fov}, Cell {cell}" if n_trajectories <= 20 else None,
        )

        # Mark start point
        ax.scatter(
            x_coords[0],
            y_coords[0],
            color=colors[idx % len(colors)],
            marker="o",
            s=30,
            alpha=0.8,
            edgecolors="black",
            linewidths=0.5,
        )

        # Mark end point
        ax.scatter(
            x_coords[-1],
            y_coords[-1],
            color=colors[idx % len(colors)],
            marker="s",
            s=30,
            alpha=0.8,
            edgecolors="black",
            linewidths=0.5,
        )

    ax.set_xlabel("X position (xc)", fontsize=12)
    ax.set_ylabel("Y position (yc)", fontsize=12)
    ax.set_title(
        f"Cell Trajectories ({n_trajectories} trajectories)",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.3)
    ax.set_aspect("equal", adjustable="box")

    # Add legend if we have reasonable number of trajectories
    if n_trajectories <= 20:
        ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize=8, ncol=1)
    else:
        # Add a note about number of trajectories
        ax.text(
            0.02,
            0.98,
            f"{n_trajectories} trajectories shown",
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
        )

    plt.tight_layout()

    # Determine output path
    if output is None:
        output = csv_path.parent / f"{csv_path.stem}_trajectories.png"
    else:
        output = output.expanduser()
        if output.is_dir():
            output = output / f"{csv_path.stem}_trajectories.png"

    # Save the plot
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)

    typer.secho(f"Trajectory plot saved to: {output}", fg=typer.colors.GREEN, bold=True)


@app.command()
def plot(
    npy_path: Path = typer.Argument(..., help="Path to numpy array file (.npy)"),
    frame: int | None = typer.Option(
        None,
        "--frame",
        "-f",
        help="Frame index to plot (for 3D arrays). If not specified, plots middle frame.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for plot (default: <npy_path>_plot.png)",
    ),
    cmap: str | None = typer.Option(
        None,
        "--cmap",
        help="Colormap to use (e.g., 'gray', 'nipy_spectral'). Auto-detected if not specified.",
    ),
    dpi: int = typer.Option(150, "--dpi", help="Resolution for saved plot"),
) -> None:
    """Plot a frame from a numpy array file for quick visualization."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    npy_path = npy_path.expanduser()
    if not npy_path.exists():
        typer.secho(f"File '{npy_path}' does not exist.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not npy_path.is_file():
        typer.secho(f"Path '{npy_path}' is not a file.", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not npy_path.suffix == ".npy":
        typer.secho(
            f"File '{npy_path}' does not have .npy extension.",
            err=True,
            fg=typer.colors.YELLOW,
        )

    typer.echo(f"Loading array from {npy_path}...")
    try:
        output_path = plot_numpy_array(
            array_path=npy_path,
            frame=frame,
            output_path=output,
            cmap=cmap,
            dpi=dpi,
        )
    except Exception as exc:
        typer.secho(f"Failed to plot array: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.secho(f"Plot saved to: {output_path}", fg=typer.colors.GREEN, bold=True)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8765, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(
        False, "--reload", "-r", help="Enable auto-reload for development"
    ),
) -> None:
    """Start the FastAPI server for the PyAMA API.

    The server provides REST endpoints for:
    - Loading microscopy file metadata
    - Getting processing configuration schema
    - Creating and managing processing tasks

    Example:
        pyama-core serve --port 8765 --reload
    """
    import uvicorn

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)

    typer.echo(f"Starting PyAMA Core API server on http://{host}:{port}")
    typer.echo("API documentation available at:")
    typer.echo(f"  - Swagger UI: http://{host}:{port}/docs")
    typer.echo(f"  - ReDoc: http://{host}:{port}/redoc")
    typer.echo("")

    uvicorn.run(
        "pyama_core.api.server:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    app()
