"""Exports for the consolidated modeling tab."""

from importlib import import_module

_EXPORTS = {
    "ModelingView": ("pyama_gui.apps.modeling.view", "ModelingView"),
    "ModelingViewModel": ("pyama_gui.apps.modeling.view_model", "ModelingViewModel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
