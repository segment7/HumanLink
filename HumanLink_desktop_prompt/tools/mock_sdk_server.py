from __future__ import annotations

import argparse
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict


SCENARIOS = {"success", "failed", "timeout"}
SESSIONS: Dict[str, Dict[str, object]] = {}


def now_s() -> float:
    return time.time()


def build_status(scenario: str, elapsed: float) -> Dict[str, object]:
    if scenario == "success":
        if elapsed < 1.0:
            return {"status": "authenticating", "device_status": "connecting", "user_prompt": "正在连接设备..."}
        if elapsed < 2.0:
            return {
                "status": "authenticating",
                "device_status": "waiting_for_biometric",
                "user_prompt": "请放置您的手指进行授权",
            }
        if elapsed < 3.0:
            return {
                "status": "authenticating",
                "device_status": "verifying",
                "verification_step": 6,
                "verification_progress": 60,
                "user_prompt": "正在进行十步验证...",
            }
        return {"status": "completed", "device_status": "success", "verification_progress": 100}

    if scenario == "failed":
        if elapsed < 1.0:
            return {"status": "authenticating", "device_status": "connecting", "user_prompt": "正在连接设备..."}
        if elapsed < 2.0:
            return {
                "status": "authenticating",
                "device_status": "waiting_for_biometric",
                "user_prompt": "请放置您的手指进行授权",
            }
        return {"status": "failed", "device_status": "error", "error": "指纹不匹配"}

    # timeout: keep non-terminal forever, let desktop app timeout itself
    if elapsed < 1.0:
        return {"status": "authenticating", "device_status": "connecting", "user_prompt": "正在连接设备..."}
    return {
        "status": "authenticating",
        "device_status": "waiting_for_biometric",
        "user_prompt": "请放置您的手指进行授权",
    }


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != "/mock/create":
            self._write(404, {"error": "not found"})
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
        payload = json.loads(body.decode("utf-8") or "{}")
        scenario = str(payload.get("scenario", "success")).strip().lower()
        if scenario not in SCENARIOS:
            self._write(400, {"error": f"invalid scenario, expected one of {sorted(SCENARIOS)}"})
            return

        session_id = str(payload.get("session_id", "")).strip() or str(uuid.uuid4())
        SESSIONS[session_id] = {"scenario": scenario, "started_at": now_s()}
        self._write(200, {"session_id": session_id, "scenario": scenario})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._write(200, {"status": "ok", "sessions": len(SESSIONS)})
            return

        prefix = "/auth/status/"
        if not self.path.startswith(prefix):
            self._write(404, {"detail": "not found"})
            return

        session_id = self.path[len(prefix) :]
        session = SESSIONS.get(session_id)
        if not session:
            self._write(404, {"detail": "Session not found"})
            return

        elapsed = now_s() - float(session["started_at"])
        payload = build_status(str(session["scenario"]), elapsed)
        self._write(200, payload)

    def _write(self, status: int, payload: Dict[str, object]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Mock HumanLink SDK server for desktop prompt demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockHandler)
    print(f"Mock SDK running at http://{args.host}:{args.port}")
    print("Create session: POST /mock/create with {\"scenario\":\"success|failed|timeout\"}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

