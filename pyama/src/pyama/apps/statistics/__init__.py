"""Lazy exports for statistics services."""

from importlib import import_module

_EXPORTS = {
    "discover_sample_pairs": (
        "pyama.apps.statistics.discovery",
        "discover_sample_pairs",
    ),
    "evaluate_onset_trace": (
        "pyama.apps.statistics.metrics",
        "evaluate_onset_trace",
    ),
    "run_folder_statistics": (
        "pyama.apps.statistics.service",
        "run_folder_statistics",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
