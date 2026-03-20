from pathlib import Path


def test_gui_and_cli_use_task_api_not_workflow_compatibility_layer() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source_roots = [
        repo_root / "pyama-cli" / "src",
        repo_root / "pyama-gui" / "src",
    ]

    forbidden_fragments = (
        "WorkflowTaskManager",
        "WorkflowProgressEvent",
        "WorkflowStatusEvent",
        "from pyama.apps.",
        "import pyama.apps.",
    )

    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for fragment in forbidden_fragments:
                assert fragment not in content, f"{fragment} found in {path}"


def test_pyama_contains_single_core_progress_helper() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    progress_files = sorted(
        path.relative_to(repo_root).as_posix()
        for path in (repo_root / "pyama" / "src" / "pyama").rglob("progress.py")
    )

    assert progress_files == ["pyama/src/pyama/utils/progress.py"]
