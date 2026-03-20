from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from pyama.utils.position import parse_position_range


class SegmentationMethod(str, Enum):
    LOGSTD = "logstd"
    CELLPOSE = "cellpose"


class TrackingMethod(str, Enum):
    IOU = "iou"
    BTRACK = "btrack"


class Channels(BaseModel):
    pc: dict[int, list[str]]
    fl: dict[int, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_single_pc_channel(self) -> "Channels":
        if len(self.pc) != 1:
            raise ValueError(f"pc must contain exactly one channel, got {len(self.pc)}")
        return self

    def get_pc_channel(self) -> int:
        return next(iter(self.pc))

    def get_pc_features(self) -> list[str]:
        return list(next(iter(self.pc.values())))


class ProcessingParams(BaseModel):
    model_config = {"extra": "forbid"}

    positions: str = Field(default="all", description="Position selection in slice syntax")
    n_workers: int = Field(default=1, ge=1)
    background_weight: float = Field(default=1.0, ge=0.0)
    background_min_samples: int = Field(default=64, ge=1)
    segmentation_method: SegmentationMethod = SegmentationMethod.LOGSTD
    tracking_method: TrackingMethod = TrackingMethod.IOU
    copy_only: bool = False

    @field_validator("positions")
    @classmethod
    def _validate_positions_syntax(cls, value: str) -> str:
        parse_position_range(value, length=None)
        return value


class ProcessingConfig(BaseModel):
    channels: Channels | None = None
    params: ProcessingParams = Field(default_factory=ProcessingParams)

