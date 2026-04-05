from __future__ import annotations

import json
import urllib.request

from humanlink_desktop_prompt.coordinator import TrackingCoordinator
from humanlink_desktop_prompt.ingress import IngressServer
from humanlink_desktop_prompt.tracker import TrackerConfig


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        body = resp.read().decode("utf-8")
        return resp.status, json.loads(body)


def test_track_endpoint_and_duplicate_idempotent():
    coordinator = TrackingCoordinator(
        tracker_config=TrackerConfig("http://127.0.0.1:8765", poll_interval_seconds=1, session_timeout_seconds=1),
        event_sink=lambda _event: None,
    )
    server = IngressServer("127.0.0.1", 0, coordinator.handle_track)
    server.start()
    try:
        url = f"http://127.0.0.1:{server.bound_port}/track"
        status1, body1 = post_json(url, {"session_id": "sess-dup"})
        status2, body2 = post_json(url, {"session_id": "sess-dup"})

        assert status1 == 200
        assert body1["accepted"] is True
        assert status2 == 200
        assert body2["accepted"] is True
        assert body1["tracking_id"] == body2["tracking_id"]
    finally:
        coordinator.stop_all()
        server.stop()

