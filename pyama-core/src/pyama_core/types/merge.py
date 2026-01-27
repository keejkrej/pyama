from pydantic import BaseModel


class MergeResult(BaseModel):
    frame: int
    fov: int
    cell: int
    value: float


def get_merge_fields() -> list[str]:
    return list(MergeResult.model_fields.keys())
