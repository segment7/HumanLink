from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class PromptStage(str, Enum):
    RISK_DETECTED = "risk_detected"
    CHALLENGE_CREATED = "challenge_created"
    CONNECTING_DEVICE = "connecting_device"
    WAITING_THUMB = "waiting_thumb"
    VERIFYING_SIGNATURE = "verifying_signature"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class PromptEvent:
    session_id: str
    tracking_id: str
    stage: PromptStage
    message: str
    progress: Optional[int] = None
    verification_step: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class TrackRequest:
    session_id: str
    risk_level: str = "high"
    display_title: str = "高危操作授权"
    display_summary: str = ""

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "TrackRequest":
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            raise ValueError("session_id is required")

        risk_level = str(payload.get("risk_level", "high")).strip() or "high"
        display_title = str(payload.get("display_title", "高危操作授权")).strip() or "高危操作授权"
        display_summary = str(payload.get("display_summary", "")).strip()

        return TrackRequest(
            session_id=session_id,
            risk_level=risk_level,
            display_title=display_title,
            display_summary=display_summary,
        )

