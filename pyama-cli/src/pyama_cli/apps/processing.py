"""Processing-domain commands for pyama-cli."""

from dataclasses import replace
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
)

from pyama.tasks import (
    MergeTaskRequest,
    ProcessingTaskRequest,
    TaskProgress,
    TaskStatus,
    submit_merge,
    submit_processing,
    subscribe,
    unsubscribe,
)
from pyama.apps.processing.merge import normalize_samples
from pyama.types import ProcessingConfig
from pyama.types.processing import Channels
from pyama.types.processing import MergeSamplePayload
from pyama_cli.apps.common import (
    collect_samples_interactively,
    configure_logging,
    create_fluorescence_feature_map,
    initialize_feature_options,
    load_metadata_for_prompt,
    print_channel_summary,
    prompt_channel,
    prompt_directory,
    prompt_features,
    prompt_int,
    prompt_microscopy_path,
)


def register_commands(app: typer.Typer) -> None:
    """Register processing-domain commands on the root CLI app."""

    @app.command()
    def workflow() -> None:
        """Run an interactive workflow wizard to process microscopy data."""
        configure_logging()
        pc_feature_options, fl_feature_options = initialize_feature_options()

        typer.echo(
            "Welcome to PyAMA workflow! Let's collect the inputs for PyAMA processing.\n"
        )
        microscopy_path = prompt_microscopy_path()
        metadata = load_metadata_for_prompt(microscopy_path)

        channel_names = metadata.channel_names or [
            f"C{i}" for i in range(metadata.n_channels)
        ]
        print_channel_summary(channel_names)

        pc_channel = prompt_channel(
            "Select the phase contrast (PC) channel index",
            range(len(channel_names)),
        )

        typer.echo(
            f"\nAvailable phase contrast features: {', '.join(pc_feature_options)}"
        )
        pc_features = prompt_features(f"PC channel [{pc_channel}]", pc_feature_options)
        typer.echo("")

        fl_feature_map = create_fluorescence_feature_map()

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
                    "Please enter a numeric channel index.",
                    err=True,
                    fg=typer.colors.RED,
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
                    (
                        f"Channel {fl_channel} is not valid. "
                        f"Available indices: {list(range(len(channel_names)))}"
                    ),
                    err=True,
                    fg=typer.colors.RED,
                )
                continue

            typer.echo(
                f"Available fluorescence features: {', '.join(fl_feature_options)}"
            )
            features = prompt_features(
                f"FL channel [{fl_channel}]",
                fl_feature_options,
            )
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
            default=str(microscopy_path.parent),
        ).strip()
        output_dir = Path(output_dir_input).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        config = ProcessingConfig(
            channels=Channels(
                pc={pc_channel: sorted(pc_features)},
                fl={
                    channel: sorted(features)
                    for channel, features in sorted(fl_feature_map.items())
                },
            ),
        )

        typer.secho("\nPrepared config:", bold=True)
        typer.echo(config)

        default_position_end = max(metadata.n_positions - 1, 0)
        position_start = prompt_int("Position start", 0, minimum=0)
        position_end = prompt_int("Position end", default_position_end, minimum=position_start)
        n_workers = prompt_int("Number of workers", 1, minimum=1)

        config = replace(
            config,
            params=replace(
                config.params,
                positions=f"{position_start}:{position_end + 1}",
                n_workers=n_workers,
            ),
        )

        typer.secho("\nStarting workflow...", bold=True)
        console = Console(stderr=True)
        record = submit_processing(
            ProcessingTaskRequest(
                metadata=metadata,
                config=config,
                output_dir=output_dir,
            )
        )
        queue = subscribe(record.id)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
                transient=True,
            ) as progress:
                overall_task = progress.add_task("Workflow progress", total=100)
                detail_task = progress.add_task("Waiting for events", total=100)
                while True:
                    snapshot = queue.get()
                    progress_state = snapshot.progress
                    if progress_state is not None:
                        _update_workflow_progress(
                            progress,
                            overall_task,
                            detail_task,
                            progress_state,
                        )
                    if snapshot.status in {
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    }:
                        success = snapshot.status == TaskStatus.COMPLETED and bool(
                            (snapshot.result or {}).get("success", False)
                        )
                        if snapshot.status != TaskStatus.COMPLETED:
                            raise RuntimeError(
                                snapshot.error_message or "Workflow failed"
                            )
                        break
        except Exception as exc:  # pragma: no cover - defensive
            typer.secho(f"Workflow failed: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc
        finally:
            unsubscribe(record.id, queue)

        status = "SUCCESS" if success else "FAILED"
        color = typer.colors.GREEN if success else typer.colors.RED
        typer.secho(f"Workflow finished: {status}", bold=True, fg=color)

    @app.command()
    def merge() -> None:
        """Run an interactive merge wizard to combine CSV outputs from samples."""
        configure_logging()
        typer.echo("Welcome to PyAMA merge! Let's gather the inputs for CSV merging.\n")

        samples = collect_samples_interactively()
        typer.echo("")

        processing_results_dir = prompt_directory(
            "Enter the run folder",
            default=Path.cwd(),
            must_exist=True,
        )
        traces_dir = processing_results_dir / "traces"
        if not traces_dir.exists():
            typer.secho(
                f"traces directory not found in {processing_results_dir}",
                err=True,
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        typer.echo("")
        typer.secho("Starting merge...", bold=True)

        sample_payloads: list[MergeSamplePayload] = [
            {"name": sample["name"], "positions": sample["positions"]} for sample in samples
        ]
        record = submit_merge(
            MergeTaskRequest(
                samples=normalize_samples(sample_payloads),
                input_dir=processing_results_dir,
                output_dir=processing_results_dir / "traces_merged",
            )
        )
        queue = subscribe(record.id)
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=Console(stderr=True),
                transient=True,
            ) as progress:
                merge_task = progress.add_task("Loading FOV CSVs", total=100)
                while True:
                    snapshot = queue.get()
                    progress_state = snapshot.progress
                    if progress_state is not None:
                        completed = progress_state.percent or 0
                        progress.update(
                            merge_task,
                            completed=completed,
                            description=progress_state.message or "Merging results",
                        )
                    if snapshot.status in {
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    }:
                        if snapshot.status != TaskStatus.COMPLETED:
                            raise RuntimeError(
                                snapshot.error_message or "Merge failed"
                            )
                        message = str((snapshot.result or {}).get("message", ""))
                        break
        except Exception as exc:  # pragma: no cover - runtime path
            typer.secho(f"Merge failed: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        finally:
            unsubscribe(record.id, queue)

        typer.secho(message, fg=typer.colors.GREEN, bold=True)


def _update_workflow_progress(
    progress: Progress,
    overall_task: TaskID,
    detail_task: TaskID,
    state: TaskProgress,
) -> None:
    def _to_int(value: object, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    completed = state.percent or 0
    progress.update(
        overall_task,
        completed=completed,
        description=state.message or state.step,
    )
    details = state.details
    step_total = max(1, _to_int(details.get("step_total", 0), 0))
    step_current = min(_to_int(details.get("step_current", 0), 0), step_total)
    worker_id = _to_int(details.get("worker_id", -1), -1)
    position = _to_int(details.get("position_id", -1), -1)
    progress.update(
        detail_task,
        total=step_total,
        completed=step_current,
        description=(
            f"worker-{worker_id} {state.step} "
            f"position-{position}: {state.message or state.step}"
        ),
    )
