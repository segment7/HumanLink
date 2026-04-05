from __future__ import annotations

import urllib.error

from humanlink_desktop_prompt.tracker import SessionTracker, TrackerConfig
from humanlink_desktop_prompt.types import PromptStage


def test_tracker_success_flow():
    sequence = [
        {"status": "authenticating", "device_status": "connecting"},
        {"status": "authenticating", "device_status": "waiting_for_biometric"},
        {"status": "authenticating", "verification_progress": 70, "verification_step": 7},
        {"status": "completed"},
    ]

    def fetcher(_base: str, _session: str):
        return sequence.pop(0)

    events = []
    finished = []
    tracker = SessionTracker(
        session_id="sess-1",
        tracking_id="track-1",
        config=TrackerConfig("http://127.0.0.1:8765", poll_interval_seconds=0.01, session_timeout_seconds=1),
        on_event=events.append,
        on_finish=finished.append,
        fetch_status=fetcher,
    )
    tracker.start()
    tracker.join(timeout=2)

    stages = [e.stage for e in events]
    assert PromptStage.CHALLENGE_CREATED in stages
    assert PromptStage.CONNECTING_DEVICE in stages
    assert PromptStage.WAITING_THUMB in stages
    assert PromptStage.VERIFYING_SIGNATURE in stages
    assert stages[-1] == PromptStage.SUCCESS
    assert finished == ["sess-1"]


def test_tracker_404_failed():
    def fetcher(_base: str, _session: str):
        raise urllib.error.HTTPError("http://x", 404, "not found", {}, None)

    events = []
    tracker = SessionTracker(
        session_id="sess-404",
        tracking_id="track-404",
        config=TrackerConfig("http://127.0.0.1:8765", poll_interval_seconds=0.01, session_timeout_seconds=1),
        on_event=events.append,
        on_finish=lambda _session: None,
        fetch_status=fetcher,
    )
    tracker.start()
    tracker.join(timeout=2)

    assert events[-1].stage == PromptStage.FAILED

