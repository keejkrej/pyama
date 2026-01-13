import dataclasses
from dataclasses import dataclass


@dataclass
class MergeResult:
    frame: int
    fov: int
    cell: int
    value: float


def get_merge_fields() -> list[str]:
    return [field.name for field in dataclasses.fields(MergeResult)]
