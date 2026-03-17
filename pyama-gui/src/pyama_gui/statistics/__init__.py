"""Lazy exports for statistics UI components."""

from importlib import import_module

_EXPORTS = {
    "StatisticsTab": ("pyama_gui.statistics.main_tab", "StatisticsTab"),
    "StatisticsLoadPanel": ("pyama_gui.statistics.load", "StatisticsLoadPanel"),
    "StatisticsDetailPanel": ("pyama_gui.statistics.detail", "StatisticsDetailPanel"),
    "StatisticsComparisonPanel": (
        "pyama_gui.statistics.comparison",
        "StatisticsComparisonPanel",
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
