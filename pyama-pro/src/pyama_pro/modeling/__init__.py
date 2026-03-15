"""Lazy exports for modeling UI components."""

from importlib import import_module

_EXPORTS = {
    "ModelingTab": ("pyama_pro.modeling.main_tab", "ModelingTab"),
    "DataPanel": ("pyama_pro.modeling.data", "DataPanel"),
    "ParameterPanel": ("pyama_pro.modeling.parameter", "ParameterPanel"),
    "QualityPanel": ("pyama_pro.modeling.quality", "QualityPanel"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


