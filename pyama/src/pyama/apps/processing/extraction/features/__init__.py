"""Cell feature extraction algorithms and registry.

Features are explicitly registered from modules in this package.
Each feature module must define an extract_* function.
"""

from collections.abc import Callable

from pyama.apps.processing.extraction.features.fluorescence import intensity
from pyama.apps.processing.extraction.features.phase_contrast import area
from pyama.types.processing import ExtractionContext

# =============================================================================
# FEATURE REGISTRATION (EXPLICIT)
# =============================================================================
# Phase-contrast features operate on segmentation / masks derived from phase images.
PHASE_FEATURES: dict[str, Callable] = {}

# Register phase contrast features
PHASE_FEATURES["area"] = area.extract_area

# Fluorescence-dependent features operate on intensity stacks per channel.
FLUORESCENCE_FEATURES: dict[str, Callable] = {}

# Register fluorescence features
FLUORESCENCE_FEATURES["intensity"] = intensity.extract_intensity

# Flattened lookup used by the extraction pipeline.
FEATURE_EXTRACTORS: dict[str, Callable] = {
    **FLUORESCENCE_FEATURES,
    **PHASE_FEATURES,
}


def list_features() -> list[str]:
    """Return all registered feature names."""
    return list(FEATURE_EXTRACTORS.keys())


def list_fluorescence_features() -> list[str]:
    """Return fluorescence-dependent features."""
    return list(FLUORESCENCE_FEATURES.keys())


def list_phase_features() -> list[str]:
    """Return phase-contrast features."""
    return list(PHASE_FEATURES.keys())


def get_feature_extractor(feature_name: str):
    """Get the feature extractor function for a given feature name."""
    return FEATURE_EXTRACTORS[feature_name]


__all__ = [
    "ExtractionContext",
    "FLUORESCENCE_FEATURES",
    "PHASE_FEATURES",
    "FEATURE_EXTRACTORS",
    "list_features",
    "list_fluorescence_features",
    "list_phase_features",
    "get_feature_extractor",
]
