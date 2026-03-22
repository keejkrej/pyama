from pyama.types.tasks import ProgressPayload
from pyama.utils.progress import (
    build_progress_payload,
    emit_progress,
)


def test_build_progress_payload_computes_percent() -> None:
    payload = build_progress_payload(
        step="analysis_fitting",
        current=3,
        total=4,
        message="Working",
        file="sample.csv",
    )

    assert payload["step"] == "analysis_fitting"
    assert payload["current"] == 3
    assert payload["total"] == 4
    assert payload["progress"] == 75
    assert payload["message"] == "Working"
    assert payload["file"] == "sample.csv"


def test_build_progress_payload_omits_percent_for_zero_total() -> None:
    payload = build_progress_payload(
        step="analysis_fitting",
        current=1,
        total=0,
        message="Working",
    )

    assert payload["progress"] is None


def test_build_progress_payload_supports_frame_aliases() -> None:
    payload = build_progress_payload(
        step="copy",
        event="frame",
        position=2,
        channel=1,
        current=5,
        total=10,
        current_key="t",
        total_key="T",
        message="Copying",
        worker_id=-1,
    )

    assert payload == {
        "event": "frame",
        "step": "copy",
        "position": 2,
        "channel": 1,
        "t": 5,
        "T": 10,
        "progress": 50,
        "message": "Copying",
        "worker_id": -1,
    }


def test_build_progress_payload_omits_channel_when_not_set() -> None:
    payload = build_progress_payload(
        step="tracking",
        event="frame",
        position=1,
        current=3,
        total=9,
        current_key="t",
        total_key="T",
        message="Tracking",
    )

    assert "channel" not in payload


def test_emit_helpers_noop_without_reporter() -> None:
    counted = emit_progress(
        None,
        step="statistics",
        current=1,
        total=2,
        message="Processed sample",
    )
    frame = emit_progress(
        None,
        step="copy",
        event="frame",
        position=0,
        current=0,
        total=5,
        current_key="t",
        total_key="T",
        message="Copying",
    )

    assert counted["progress"] == 50
    assert frame["step"] == "copy"


def test_emit_helpers_forward_payloads_to_reporter() -> None:
    seen: list[ProgressPayload] = []

    emit_progress(
        seen.append,
        step="statistics",
        current=2,
        total=5,
        message="Processed sample B",
    )
    emit_progress(
        step="segmentation",
        reporter=seen.append,
        event="frame",
        position=4,
        current=7,
        total=10,
        current_key="t",
        total_key="T",
        message="Segmentation",
    )

    assert seen[0]["progress"] == 40
    assert seen[1]["event"] == "frame"
