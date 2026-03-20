"""Base production/decay model used for trace fitting."""

import numpy as np

from pyama.apps.modeling.models.preset import (
    DEFAULT_PROTEIN_DEGRADATION_RATE_MIN,
    list_protein_presets,
)
from pyama.types.modeling import ModelParameter


PARAMETERS: dict[str, ModelParameter] = {
    "protein_degradation_rate_min": ModelParameter(
        key="protein_degradation_rate_min",
        name="Protein Degradation Rate (1/min)",
        value=DEFAULT_PROTEIN_DEGRADATION_RATE_MIN,
        mode="fixed",
        is_interest=False,
        presets=list_protein_presets(),
    ),
    "time_onset_min": ModelParameter(
        key="time_onset_min",
        name="Time Onset",
        value=120.0,
        mode="fit",
        is_interest=True,
        lb=-1e6,
        ub=1800.0,
    ),
    "ktl_m0_min": ModelParameter(
        key="ktl_m0_min",
        name="Combined Production (1/min)",
        value=20.0 / 60.0,
        mode="fit",
        is_interest=False,
        lb=1.0 / 60.0,
        ub=5e4 / 60.0,
    ),
    "mrna_degradation_rate_min": ModelParameter(
        key="mrna_degradation_rate_min",
        name="mRNA Degradation Rate (1/min)",
        value=0.07 / 60.0,
        mode="fit",
        is_interest=True,
        lb=1e-5 / 60.0,
        ub=10.1 / 60.0,
    ),
    "intensity_offset": ModelParameter(
        key="intensity_offset",
        name="Intensity Offset",
        value=0.0,
        mode="fit",
        is_interest=False,
        lb=-1e6,
        ub=1e6,
    ),
}


def get_parameters() -> dict[str, ModelParameter]:
    """Return fresh parameter definitions for the base model."""
    return {key: param.clone() for key, param in PARAMETERS.items()}


def get_fixed_parameters() -> dict[str, ModelParameter]:
    """Return parameters that remain fixed during fitting."""
    return {
        key: param.clone()
        for key, param in PARAMETERS.items()
        if param.mode == "fixed"
    }


def get_fit_parameters() -> dict[str, ModelParameter]:
    """Return parameters that are optimized during fitting."""
    return {
        key: param.clone()
        for key, param in PARAMETERS.items()
        if param.mode == "fit"
    }


def eval(
    t: np.ndarray,
    fixed: dict[str, ModelParameter],
    fit: dict[str, ModelParameter],
) -> np.ndarray:
    """Evaluate the base closed-form model in minutes."""
    time_min = np.asarray(t, dtype=np.float64)
    time_onset_min = fit["time_onset_min"].value
    ktl_m0_min = fit["ktl_m0_min"].value
    mrna_degradation_rate_min = fit["mrna_degradation_rate_min"].value
    protein_degradation_rate_min = fixed["protein_degradation_rate_min"].value
    intensity_offset = fit["intensity_offset"].value

    tau = time_min - time_onset_min
    result = np.full_like(time_min, float(intensity_offset), dtype=np.float64)
    active = tau > 0
    if not np.any(active):
        return result

    tau_active = tau[active]
    rate_difference = (
        protein_degradation_rate_min - mrna_degradation_rate_min
    )
    if abs(rate_difference) < 1e-9:
        response = (
            ktl_m0_min
            * tau_active
            * np.exp(-protein_degradation_rate_min * tau_active)
        )
    else:
        response = (ktl_m0_min / rate_difference) * (
            np.exp(-mrna_degradation_rate_min * tau_active)
            - np.exp(-protein_degradation_rate_min * tau_active)
        )
    result[active] = intensity_offset + response
    return result
