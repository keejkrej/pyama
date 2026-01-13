"""
Simple functional models for curve fitting.
"""

from pyama_core.analysis.models import maturation

_MODELS = {
    "maturation": maturation,
}


def get_model(model_name: str):
    model_name_lower = model_name.lower()
    if model_name_lower not in _MODELS:
        available = ", ".join(_MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return _MODELS[model_name_lower]


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
    return list(_MODELS.keys())


def register_plugin_model(model_name: str, model_module: object) -> None:
    """Register a plugin model at runtime.

    Args:
        model_name: Name of the model (e.g., "exponential_decay")
        model_module: Module with Params, Bounds, DEFAULTS, BOUNDS, eval

    Raises:
        ValueError: If model_name already registered or module is invalid
    """
    if model_name in _MODELS:
        raise ValueError(
            f"Model '{model_name}' is already registered. "
            f"Plugin models must have unique names."
        )

    # Verify required components
    required = ["Params", "Bounds", "DEFAULTS", "BOUNDS", "eval"]
    for attr in required:
        if not hasattr(model_module, attr):
            raise ValueError(f"Model module missing required attribute: {attr}")

    _MODELS[model_name] = model_module


__all__ = [
    "get_model",
    "get_types",
    "list_models",
    "register_plugin_model",
]
