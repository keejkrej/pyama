"""Exports for the consolidated processing tab."""

from importlib import import_module

_EXPORTS = {
    "ProcessingView": ("pyama_gui.processing.view", "ProcessingView"),
    "ProcessingViewModel": ("pyama_gui.processing.view_model", "ProcessingViewModel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
