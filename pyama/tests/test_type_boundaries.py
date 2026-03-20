from pathlib import Path

import pytest

from pyama.apps.processing.merge import normalize_samples, read_samples_yaml
from pyama.types.processing import (
    ChannelSelection,
    Channels,
    MergeSample,
    ProcessingContext,
    ProcessingParams,
    ensure_context,
)


def test_channel_models_reject_loose_constructor_inputs() -> None:
    with pytest.raises(TypeError):
        ChannelSelection(channel="0", features=["area"])  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        Channels(pc={"channel": 0, "features": ["area"]})  # type: ignore[arg-type]


def test_channel_payload_round_trip_uses_dict_payloads() -> None:
    channels = Channels(
        pc=ChannelSelection(channel=0, features=["area"]),
        fl=[ChannelSelection(channel=1, features=["intensity"])],
    )

    payload = channels.to_payload()

    assert payload == {
        "pc": {"channel": 0, "features": ["area"]},
        "fl": [{"channel": 1, "features": ["intensity"]}],
    }
    assert Channels.from_payload(payload) == channels


def test_ensure_context_requires_processing_params_dataclass() -> None:
    with pytest.raises(TypeError):
        ensure_context(
            ProcessingContext(
                output_dir=Path.cwd(),
                channels=Channels(),
                params={"background_weight": 0.5},  # type: ignore[arg-type]
            )
        )

    context = ensure_context(ProcessingContext(output_dir=Path.cwd()))
    assert isinstance(context.params, ProcessingParams)


def test_merge_yaml_parses_payload_then_normalizes_to_dataclasses(tmp_path: Path) -> None:
    sample_file = tmp_path / "samples.yaml"
    sample_file.write_text(
        "samples:\n"
        "  - name: sample_a\n"
        "    fovs: 0-2\n"
        "  - name: sample_b\n"
        "    fovs: [4, 5]\n",
        encoding="utf-8",
    )

    payload = read_samples_yaml(sample_file)
    samples = normalize_samples(payload["samples"])

    assert payload == {
        "samples": [
            {"name": "sample_a", "fovs": "0-2"},
            {"name": "sample_b", "fovs": [4, 5]},
        ]
    }
    assert samples == [
        MergeSample(name="sample_a", fovs=(0, 1, 2)),
        MergeSample(name="sample_b", fovs=(4, 5)),
    ]
