"""Modeling types for model fitting."""

from dataclasses import dataclass, replace
from typing import Literal


@dataclass(frozen=True, slots=True)
class ParameterPreset:
    """Named preset for a model parameter."""

    key: str
    name: str
    value: float


@dataclass(frozen=True, slots=True)
class ModelParameter:
    """A model parameter definition or resolved runtime value."""

    key: str
    name: str
    value: float
    mode: Literal["fit", "fixed"]
    is_interest: bool
    lb: float | None = None
    ub: float | None = None
    presets: tuple[ParameterPreset, ...] = ()

    @property
    def has_presets(self) -> bool:
        return bool(self.presets)

    def clone(
        self,
        *,
        value: float | None = None,
        lb: float | None = None,
        ub: float | None = None,
    ) -> "ModelParameter":
        """Return a copy with optional runtime overrides applied."""
        return replace(
            self,
            value=self.value if value is None else value,
            lb=self.lb if lb is None else lb,
            ub=self.ub if ub is None else ub,
        )


@dataclass(frozen=True, slots=True)
class FittingResult:
    """Result of model fitting."""

    fixed_params: dict[str, ModelParameter]
    fitted_params: dict[str, ModelParameter]
    success: bool
    r_squared: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert result to flat dictionary of parameter values."""
        result = {}
        for param_name, param in self.fixed_params.items():
            result[param_name] = param.value
        for param_name, param in self.fitted_params.items():
            result[param_name] = param.value
        return result
