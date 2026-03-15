"""Lazy exports for processing UI components."""

from importlib import import_module

_EXPORTS = {
    "ProcessingTab": ("pyama_pro.processing.main_tab", "ProcessingTab"),
    "InputPanel": ("pyama_pro.processing.input", "InputPanel"),
    "MergePanel": ("pyama_pro.processing.merge", "MergePanel"),
    "OutputPanel": ("pyama_pro.processing.output", "OutputPanel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
