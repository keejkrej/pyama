from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, computed_field


class MicroscopyMetadata(BaseModel):
    file_path: Path
    base_name: str
    file_type: str
    height: int
    width: int
    n_frames: int
    channel_names: tuple[str, ...]
    dtype: str
    timepoints: tuple[float, ...] = Field(default_factory=tuple)
    position_list: tuple[int, ...] = Field(
        default_factory=lambda: (0,),
        validation_alias=AliasChoices("position_list", "fov_list"),
    )

    @computed_field
    @property
    def n_positions(self) -> int:
        return len(self.position_list)

    @computed_field
    @property
    def n_channels(self) -> int:
        return len(self.channel_names)

    @computed_field
    @property
    def fov_list(self) -> tuple[int, ...]:
        return self.position_list

    @computed_field
    @property
    def n_fovs(self) -> int:
        return self.n_positions
