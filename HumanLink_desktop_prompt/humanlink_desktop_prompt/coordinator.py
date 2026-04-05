from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from .tracker import SessionTracker, TrackerConfig
from .types import PromptEvent, PromptStage, TrackRequest


EventSink = Callable[[PromptEvent], None]


@dataclass
class SessionRecord:
    tracking_id: str
    tracker: SessionTracker


class TrackingCoordinator:
    def __init__(self, tracker_config: TrackerConfig, event_sink: EventSink) -> None:
        self.tracker_config = tracker_config
        self.event_sink = event_sink
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionRecord] = {}

    def handle_track(self, payload: Dict[str, object]) -> Tuple[int, Dict[str, object]]:
        try:
            req = TrackRequest.from_payload(payload)
        except ValueError as exc:
            return 400, {"accepted": False, "error": str(exc)}

        with self._lock:
            existing = self._sessions.get(req.session_id)
            if existing:
                return 200, {
                    "accepted": True,
                    "session_id": req.session_id,
                    "tracking_id": existing.tracking_id,
                }

            tracking_id = uuid.uuid4().hex
            tracker = SessionTracker(
                session_id=req.session_id,
                tracking_id=tracking_id,
                config=self.tracker_config,
                on_event=self.event_sink,
                on_finish=self._on_tracker_finish,
            )
            self._sessions[req.session_id] = SessionRecord(tracking_id=tracking_id, tracker=tracker)

        self.event_sink(
            PromptEvent(
                session_id=req.session_id,
                tracking_id=tracking_id,
                stage=PromptStage.RISK_DETECTED,
                message="检测到高危操作",
            )
        )
        tracker.start()

        return 200, {"accepted": True, "session_id": req.session_id, "tracking_id": tracking_id}

    def stop_all(self) -> None:
        with self._lock:
            records = list(self._sessions.values())
            self._sessions.clear()
        for record in records:
            record.tracker.stop()

    def _on_tracker_finish(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

