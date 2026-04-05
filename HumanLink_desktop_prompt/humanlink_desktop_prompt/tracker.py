from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from .mapper import map_sdk_status
from .types import PromptEvent, PromptStage


FetchStatusFn = Callable[[str, str], Dict[str, object]]
EventCallback = Callable[[PromptEvent], None]
FinishCallback = Callable[[str], None]


@dataclass(frozen=True)
class TrackerConfig:
    sdk_base_url: str
    poll_interval_seconds: float = 0.5
    session_timeout_seconds: float = 45.0


class SessionTracker(threading.Thread):
    def __init__(
        self,
        session_id: str,
        tracking_id: str,
        config: TrackerConfig,
        on_event: EventCallback,
        on_finish: FinishCallback,
        fetch_status: Optional[FetchStatusFn] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.session_id = session_id
        self.tracking_id = tracking_id
        self.config = config
        self.on_event = on_event
        self.on_finish = on_finish
        self.fetch_status = fetch_status or _default_fetch_status
        self._stop = threading.Event()
        self._last_key: Optional[str] = None

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        start = time.time()
        try:
            self._emit(PromptStage.CHALLENGE_CREATED, "正在发起认证 / challenge 已生成")

            while not self._stop.is_set():
                elapsed = time.time() - start
                if elapsed >= self.config.session_timeout_seconds:
                    self._emit(PromptStage.TIMEOUT, "认证超时", force=True)
                    break

                try:
                    payload = self.fetch_status(self.config.sdk_base_url, self.session_id)
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        self._emit(PromptStage.FAILED, "认证失败：会话不存在", force=True)
                        break
                    time.sleep(self.config.poll_interval_seconds)
                    continue
                except (urllib.error.URLError, TimeoutError, ValueError):
                    time.sleep(self.config.poll_interval_seconds)
                    continue

                stage, message, progress, verification_step, terminal = map_sdk_status(payload)
                self._emit(stage, message, progress=progress, verification_step=verification_step)
                if terminal:
                    break

                time.sleep(self.config.poll_interval_seconds)
        finally:
            self.on_finish(self.session_id)

    def _emit(
        self,
        stage: PromptStage,
        message: str,
        progress: Optional[int] = None,
        verification_step: Optional[int] = None,
        force: bool = False,
    ) -> None:
        key = f"{stage.value}:{progress}:{verification_step}:{message}"
        if not force and key == self._last_key:
            return
        self._last_key = key
        self.on_event(
            PromptEvent(
                session_id=self.session_id,
                tracking_id=self.tracking_id,
                stage=stage,
                message=message,
                progress=progress,
                verification_step=verification_step,
            )
        )


def _default_fetch_status(sdk_base_url: str, session_id: str) -> Dict[str, object]:
    base = sdk_base_url.rstrip("/")
    url = f"{base}/auth/status/{session_id}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = resp.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("invalid sdk status payload")
    return payload

