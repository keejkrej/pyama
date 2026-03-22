"""Processing-domain payload types."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypedDict

from pyama.utils.position import parse_position_range


def _validate_channel_id(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("channel ids must be ints")
    return int(value)


def _normalize_feature_map(value: Mapping[object, object], *, require_single: bool = False) -> dict[int, list[str]]:
    normalized: dict[int, list[str]] = {}
    for key, features in value.items():
        channel_id = _validate_channel_id(key)
        if not isinstance(features, list):
            raise TypeError("feature collections must be lists")
        if any(not isinstance(feature, str) for feature in features):
            raise TypeError("feature names must be strings")
        normalized[channel_id] = list(features)
    if require_single and len(normalized) != 1:
        raise ValueError(f"pc must contain exactly one channel, got {len(normalized)}")
    return normalized


@dataclass(frozen=True, slots=True)
class Channels:
    pc: dict[int, list[str]]
    fl: dict[int, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_pc = _normalize_feature_map(self.pc, require_single=True)
        normalized_fl = _normalize_feature_map(self.fl)
        object.__setattr__(self, "pc", normalized_pc)
        object.__setattr__(self, "fl", normalized_fl)

    def get_pc_channel(self) -> int:
        return next(iter(self.pc))

    def get_pc_features(self) -> list[str]:
        return list(next(iter(self.pc.values())))

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "Channels":
        pc = data.get("pc")
        fl = data.get("fl", {})
        if not isinstance(pc, Mapping):
            raise TypeError("channels.pc must be a mapping")
        if not isinstance(fl, Mapping):
            raise TypeError("channels.fl must be a mapping")
        return cls(pc=dict(pc), fl=dict(fl))

    def to_dict(self) -> dict[str, object]:
        return {
            "pc": {channel: list(features) for channel, features in self.pc.items()},
            "fl": {channel: list(features) for channel, features in self.fl.items()},
        }


@dataclass(frozen=True, slots=True)
class ProcessingParams:
    positions: str = "all"
    n_workers: int = 1
    background_weight: float = 1.0
    background_min_samples: int = 64
    copy_only: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.positions, str):
            raise TypeError("positions must be a string")
        parse_position_range(self.positions, length=None)
        if self.n_workers < 1:
            raise ValueError("n_workers must be >= 1")
        if self.background_weight < 0:
            raise ValueError("background_weight must be >= 0")
        if self.background_min_samples < 1:
            raise ValueError("background_min_samples must be >= 1")

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProcessingParams":
        return cls(
            positions=str(data.get("positions", "all")),
            n_workers=int(data.get("n_workers", 1)),
            background_weight=float(data.get("background_weight", 1.0)),
            background_min_samples=int(data.get("background_min_samples", 64)),
            copy_only=bool(data.get("copy_only", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "positions": self.positions,
            "n_workers": self.n_workers,
            "background_weight": self.background_weight,
            "background_min_samples": self.background_min_samples,
            "copy_only": self.copy_only,
        }


@dataclass(frozen=True, slots=True)
class ProcessingConfig:
    channels: Channels | None = None
    params: ProcessingParams = field(default_factory=ProcessingParams)

    def __post_init__(self) -> None:
        channels = self.channels
        if channels is not None and not isinstance(channels, Channels):
            if not isinstance(channels, Mapping):
                raise TypeError("channels must be a Channels instance, mapping, or None")
            channels = Channels.from_dict(channels)
            object.__setattr__(self, "channels", channels)
        params = self.params
        if not isinstance(params, ProcessingParams):
            if not isinstance(params, Mapping):
                raise TypeError("params must be a ProcessingParams instance or mapping")
            params = ProcessingParams.from_dict(params)
            object.__setattr__(self, "params", params)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "ProcessingConfig":
        channels_value = data.get("channels")
        params_value = data.get("params", {})
        channels = None
        if channels_value is not None:
            if not isinstance(channels_value, Mapping):
                raise TypeError("channels must be a mapping")
            channels = Channels.from_dict(channels_value)
        if isinstance(params_value, ProcessingParams):
            params = params_value
        else:
            if not isinstance(params_value, Mapping):
                raise TypeError("params must be a mapping")
            params = ProcessingParams.from_dict(params_value)
        return cls(channels=channels, params=params)

    def to_dict(self) -> dict[str, object]:
        return {
            "channels": None if self.channels is None else self.channels.to_dict(),
            "params": self.params.to_dict(),
        }


class MergeSamplePayload(TypedDict):
    name: str
    positions: str | list[int | str]


class SamplesFilePayload(TypedDict):
    samples: list[MergeSamplePayload]


@dataclass(frozen=True, slots=True)
class MergeSample:
    name: str
    positions: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("sample name must not be empty")
        if any(position < 0 for position in self.positions):
            raise ValueError("sample position values must be >= 0")

    def to_payload(self) -> MergeSamplePayload:
        return {
            "name": self.name,
            "positions": list(self.positions),
        }

__all__ = [
    "Channels",
    "MergeSample",
    "MergeSamplePayload",
    "ProcessingConfig",
    "ProcessingParams",
    "SamplesFilePayload",
]
