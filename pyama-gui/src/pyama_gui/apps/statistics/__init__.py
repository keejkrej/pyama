"""Exports for the consolidated statistics tab."""

from importlib import import_module

_EXPORTS = {
    "StatisticsView": ("pyama_gui.apps.statistics.view", "StatisticsView"),
    "StatisticsViewModel": ("pyama_gui.apps.statistics.view_model", "StatisticsViewModel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
