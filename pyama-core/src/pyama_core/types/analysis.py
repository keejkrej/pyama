"""
Analysis types for model fitting and event detection.
"""

from typing import TypeAlias

from pydantic import BaseModel


class EventResult(BaseModel):
    """Result of event detection."""

    event_detected: bool
    event_time: float | None
    event_magnitude: float | None
    confidence: float  # 0.0-1.0, higher is more confident
    event_index: int | None = None  # Frame index of event
    cusum_pos_peak: float | None = None  # Peak of positive CUSUM (for diagnostics)
    cusum_neg_peak: float | None = None  # Peak of negative CUSUM (for diagnostics)


class FixedParam(BaseModel):
    """A single fixed parameter with just a value."""
    name: str
    value: float


class FitParam(BaseModel):
    """A single parameter to be fitted with value and bounds."""
    name: str
    value: float
    lb: float
    ub: float


# Type aliases for parameter dictionaries
FixedParams: TypeAlias = dict[str, FixedParam]
FitParams: TypeAlias = dict[str, FitParam]


class FittingResult(BaseModel):
    """Result of model fitting."""
    fixed_params: FixedParams
    fitted_params: FitParams
    success: bool
    r_squared: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert result to flat dictionary of parameter values."""
        result = {}
        # Add fixed parameters
        for param_name, param in self.fixed_params.items():
            result[param_name] = param.value
        # Add fit parameters
        for param_name, param in self.fitted_params.items():
            result[param_name] = param.value
        return result
