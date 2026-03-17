"""
Simple functional models for curve fitting.
"""

from pyama.apps.modeling.models import maturation

MODELS = {
    "maturation": maturation,
}


def get_model(model_name: str):
    if model_name not in MODELS:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return MODELS[model_name]


def get_types(model_name: str):
    """Get type classes for a model.

    Returns UserParams and UserBounds for validation.
    Models with FixedParams/FitParams structure will have these types.
    """
    model = get_model(model_name)
    types = {}

    # Check for new structure (FixedParams/FitParams)
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
