"""Lazy exports for modeling utilities."""

from importlib import import_module

_EXPORTS = {
    "MODELS": ("pyama_core.modeling.models", "MODELS"),
    "FittingService": ("pyama_core.modeling.fitting_service", "FittingService"),
    "analyze_fitting_quality": (
        "pyama_core.modeling.fitting",
        "analyze_fitting_quality",
    ),
    "fit_model": ("pyama_core.modeling.fitting", "fit_model"),
    "fit_trace_data": ("pyama_core.modeling.fitting", "fit_trace_data"),
    "get_model": ("pyama_core.modeling.models", "get_model"),
    "get_types": ("pyama_core.modeling.models", "get_types"),
    "list_models": ("pyama_core.modeling.models", "list_models"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = _EXPORTS[name]
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


