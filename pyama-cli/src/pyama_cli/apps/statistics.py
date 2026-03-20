"""Statistics-domain commands for pyama-cli."""

from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from pyama.tasks import (
    StatisticsTaskRequest,
    TaskStatus,
    submit_statistics,
    subscribe,
    unsubscribe,
)
from pyama_cli.apps.common import configure_logging, prompt_directory


def register_commands(app: typer.Typer) -> None:
    """Register statistics commands on the root CLI app."""

    @app.command()
    def statistics() -> None:
        """Run an interactive statistics wizard on a merged results folder."""
        configure_logging()
        typer.echo("Welcome to PyAMA statistics. Configure the analysis inputs below.\n")

        folder_path = prompt_directory(
            "Enter the traces_merged folder",
            default=Path.cwd(),
            must_exist=True,
        )

        while True:
            mode_input = (
                typer.prompt(
                    "Statistics mode (`auc` or `onset`)",
                    default="auc",
                )
                .strip()
                .lower()
            )
            if mode_input in {"auc", "onset", "onset_shifted_relu"}:
                break
            typer.secho(
                "Supported modes are `auc` and `onset`.",
                err=True,
                fg=typer.colors.RED,
            )

        mode = "onset_shifted_relu" if mode_input == "onset" else mode_input
        normalize_by_area = typer.confirm("Normalize by area?", default=True)

        frame_interval_minutes = float(
            typer.prompt("Time interval in minutes", default=10.0)
        )

        fit_window_min = 240.0
        if mode == "onset_shifted_relu":
            fit_window_min = float(
                typer.prompt("Onset fit window in minutes", default=240.0)
            )

        area_filter_size = 10
        if normalize_by_area:
            area_filter_size = int(typer.prompt("Area filter size", default=10))

        typer.echo("")
        typer.secho("Starting statistics...", bold=True)

        record = submit_statistics(
            StatisticsTaskRequest(
                mode=mode,
                folder_path=folder_path,
                normalize_by_area=normalize_by_area,
                frame_interval_minutes=frame_interval_minutes,
                fit_window_min=fit_window_min,
                area_filter_size=area_filter_size,
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
                task_id = progress.add_task("Running statistics", total=100)
                while True:
                    snapshot = queue.get()
                    progress_state = snapshot.progress
                    if progress_state is not None:
                        progress.update(
                            task_id,
                            completed=progress_state.percent or 0,
                            description=progress_state.message or "Running statistics",
                        )
                    if snapshot.status in {
                        TaskStatus.COMPLETED,
                        TaskStatus.FAILED,
                        TaskStatus.CANCELLED,
                    }:
                        if snapshot.status != TaskStatus.COMPLETED:
                            raise RuntimeError(
                                snapshot.error_message or "Statistics failed"
                            )
                        results_df, _, output_path = snapshot.result
                        break
        except Exception as exc:  # pragma: no cover - runtime path
            typer.secho(f"Statistics failed: {exc}", err=True, fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        finally:
            unsubscribe(record.id, queue)

        typer.secho(
            f"Statistics saved to {output_path} ({len(results_df)} rows)",
            fg=typer.colors.GREEN,
            bold=True,
        )
