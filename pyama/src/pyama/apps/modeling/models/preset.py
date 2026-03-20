from pyama.types import ParameterPreset


DEFAULT_PROTEIN_DEGRADATION_RATE_MIN = 0.0436275356035 / 60.0


PROTEIN_PRESETS: dict[str, ParameterPreset] = {
    "gfp": ParameterPreset(
        key="gfp",
        name="GFP",
        value=DEFAULT_PROTEIN_DEGRADATION_RATE_MIN,
    ),
    "dsred": ParameterPreset(
        key="dsred",
        name="DsRed",
        value=DEFAULT_PROTEIN_DEGRADATION_RATE_MIN,
    ),
}


def list_protein_presets() -> tuple[ParameterPreset, ...]:
    return tuple(PROTEIN_PRESETS.values())
