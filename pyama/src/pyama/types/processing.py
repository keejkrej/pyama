"""Processing-related payloads that remain live after the pipeline cutover."""

from dataclasses import dataclass
from typing import TypedDict


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


@dataclass(frozen=True, slots=True)
class Result:
    roi: int
    frame: int
    is_good: bool
    x: float
    y: float
    w: float
    h: float


__all__ = [
    "MergeSample",
    "MergeSamplePayload",
    "Result",
    "SamplesFilePayload",
]
