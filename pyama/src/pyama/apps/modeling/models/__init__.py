"""Simple functional models for curve fitting."""

from . import base

MODELS = {
    "base": base,
}


def get_model(model_name: str):
    if model_name not in MODELS:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return MODELS[model_name]


def get_types(model_name: str):
    """Get type classes for a model.

    Returns UserParams and UserBounds for validation.
    Models may optionally expose legacy validation helper types.
    """
    model = get_model(model_name)
    types = {}

    if hasattr(model, "UserParams"):
        types["UserParams"] = model.UserParams
    if hasattr(model, "UserBounds"):
        types["UserBounds"] = model.UserBounds

    return types


def list_models() -> list[str]:
    """Return all registered model names."""
    return list(MODELS.keys())


__all__ = [
    "get_model",
    "get_types",
    "list_models",
    "MODELS",
]
