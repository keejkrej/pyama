"""Lazy exports for visualization UI components."""

from importlib import import_module

_EXPORTS = {
    "VisualizationTab": ("pyama_pro.visualization.main_tab", "VisualizationTab"),
    "ImagePanel": ("pyama_pro.visualization.image", "ImagePanel"),
    "LoadPanel": ("pyama_pro.visualization.load", "LoadPanel"),
    "TracePanel": ("pyama_pro.visualization.trace", "TracePanel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
