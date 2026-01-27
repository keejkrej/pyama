"""Analysis-related data structures."""

# =============================================================================
# IMPORTS
# =============================================================================

from pydantic import BaseModel, Field

# =============================================================================
# DATA STRUCTURES
# =============================================================================


class FittingRequest(BaseModel):
    """Parameters for triggering a fitting job."""

    model_type: str
    model_params: dict[str, float] = Field(default_factory=dict)
    model_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
