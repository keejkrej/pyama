from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pyama.io import (
    get_microscopy_channel_stack,
    get_microscopy_frame,
    get_microscopy_time_stack,
    load_microscopy_file,
)


class _ComputedArray:
    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def compute(self) -> np.ndarray:
        return self._array


class _DaskLikeArray:
    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def __getitem__(self, index) -> _ComputedArray:
        return _ComputedArray(self._array[index])


class _FakeNd2File:
    def __init__(self, path: str) -> None:
        self.path = path
        self.sizes = {"P": 2, "T": 3, "C": 2, "Y": 2, "X": 3}
        self._array = np.arange(2 * 3 * 2 * 2 * 3, dtype=np.uint16).reshape(
            2, 3, 2, 2, 3
        )
        self.metadata = SimpleNamespace(
            channels=[
                SimpleNamespace(channel=SimpleNamespace(name="Phase")),
                SimpleNamespace(channel=SimpleNamespace(name="GFP")),
            ]
        )
        self.dtype = self._array.dtype
        self.shape = self._array.shape
        self.closed = False

    def to_dask(self) -> _DaskLikeArray:
        return _DaskLikeArray(self._array)

    def events(self) -> list[dict[str, float]]:
        return [{"Time": 0.0}, {"Time": 5.0}, {"Time": 10.0}]

    def close(self) -> None:
        self.closed = True


class _FakeNd2FileFallback(_FakeNd2File):
    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.metadata = None

    def events(self):
        raise RuntimeError("missing events")


@dataclass
class _Rect:
    h: int
    w: int


class _FakeCziReader:
    def __init__(self, path: str) -> None:
        self.path = path
        self.total_bounding_box_no_pyramid = {
            "T": (0, 3),
            "C": (0, 2),
            "Y": (0, 2),
            "X": (0, 3),
        }
        self.scenes_bounding_rectangle_no_pyramid = {
            10: _Rect(h=2, w=3),
            20: _Rect(h=2, w=3),
        }
        self.metadata = {
            "ImageDocument": {
                "Metadata": {
                    "Information": {
                        "Image": {
                            "Dimensions": {
                                "Channels": {
                                    "Channel": [
                                        {"@Name": "Brightfield"},
                                        {"@Name": "Fluor"},
                                    ]
                                }
                            }
                        },
                        "Timeline": {
                            "Frame": [
                                {"@DeltaT": "1.5"},
                                {"@DeltaT": "3.0"},
                                {"@DeltaT": "4.5"},
                            ]
                        },
                    }
                }
            }
        }
        self.closed = False

    def read(self, scene: int | None = None, plane: dict[str, int] | None = None):
        plane = plane or {}
        time_idx = plane.get("T", 0)
        channel_idx = plane.get("C", 0)
        scene_value = 0 if scene is None else scene
        value = scene_value + (10 * channel_idx) + time_idx
        return np.full((2, 3), value, dtype=np.uint16)

    def close(self) -> None:
        self.closed = True


class _FakeCziReaderMismatch(_FakeCziReader):
    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.scenes_bounding_rectangle_no_pyramid = {
            10: _Rect(h=2, w=3),
            20: _Rect(h=4, w=5),
        }


def test_load_nd2_metadata_and_stacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyama.io.microscopy.nd2.ND2File", _FakeNd2File)

    reader, metadata = load_microscopy_file(Path("sample.nd2"))

    assert metadata.file_type == "nd2"
    assert metadata.fov_list == (0, 1)
    assert metadata.n_fovs == 2
    assert metadata.n_channels == 2
    assert metadata.channel_names == ("Phase", "GFP")
    assert metadata.timepoints == (0.0, 5.0, 10.0)
    assert reader.shape == (2, 3, 2, 2, 3)

    frame = get_microscopy_frame(reader, 1, 1, 2)
    assert frame.shape == (2, 3)
    assert np.array_equal(frame, np.array([[66, 67, 68], [69, 70, 71]], dtype=np.uint16))

    channel_stack = get_microscopy_channel_stack(reader, 0, 1)
    assert channel_stack.shape == (2, 2, 3)
    assert np.array_equal(
        channel_stack[0], np.array([[12, 13, 14], [15, 16, 17]], dtype=np.uint16)
    )

    time_stack = get_microscopy_time_stack(reader, 0, 1)
    assert time_stack.shape == (3, 2, 3)
    assert np.array_equal(
        time_stack[2], np.array([[30, 31, 32], [33, 34, 35]], dtype=np.uint16)
    )

    reader.close()
    assert reader.closed is True


def test_load_nd2_fallback_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyama.io.microscopy.nd2.ND2File", _FakeNd2FileFallback)

    _, metadata = load_microscopy_file(Path("fallback.nd2"))

    assert metadata.channel_names == ("C0", "C1")
    assert metadata.timepoints == (0.0, 1.0, 2.0)


def test_load_czi_metadata_and_stacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pyama.io.microscopy.czi_api.CziReader", _FakeCziReader)

    reader, metadata = load_microscopy_file(Path("sample.czi"))

    assert metadata.file_type == "czi"
    assert metadata.fov_list == (0, 1)
    assert metadata.n_fovs == 2
    assert metadata.n_channels == 2
    assert metadata.height == 2
    assert metadata.width == 3
    assert metadata.channel_names == ("Brightfield", "Fluor")
    assert metadata.timepoints == (1.5, 3.0, 4.5)

    frame = get_microscopy_frame(reader, 1, 1, 2)
    assert np.array_equal(frame, np.full((2, 3), 32, dtype=np.uint16))

    channel_stack = get_microscopy_channel_stack(reader, 0, 1)
    assert channel_stack.shape == (2, 2, 3)
    assert np.array_equal(channel_stack[1], np.full((2, 3), 21, dtype=np.uint16))

    time_stack = get_microscopy_time_stack(reader, 0, 0)
    assert time_stack.shape == (3, 2, 3)
    assert np.array_equal(time_stack[2], np.full((2, 3), 12, dtype=np.uint16))

    reader.close()
    assert reader.closed is True


def test_czi_scene_size_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pyama.io.microscopy.czi_api.CziReader", _FakeCziReaderMismatch
    )

    with pytest.raises(RuntimeError, match="identical layer-0 dimensions"):
        load_microscopy_file(Path("mismatch.czi"))


def test_load_microscopy_file_rejects_unknown_suffix() -> None:
    with pytest.raises(ValueError, match="Only \\.nd2 and \\.czi are supported"):
        load_microscopy_file(Path("sample.tif"))
