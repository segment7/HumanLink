from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional, Tuple


TrackHandler = Callable[[Dict[str, object]], Tuple[int, Dict[str, object]]]


class IngressServer:
    def __init__(self, host: str, port: int, on_track: TrackHandler) -> None:
        self.host = host
        self.port = port
        self.on_track = on_track
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def bound_port(self) -> int:
        if not self._server:
            return self.port
        return int(self._server.server_address[1])

    def start(self) -> None:
        if self._server:
            return
        handler_cls = self._build_handler()
        self._server = ThreadingHTTPServer((self.host, self.port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._server:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    def _build_handler(self):
        on_track = self.on_track

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                if self.path != "/track":
                    self._write(404, {"accepted": False, "error": "not found"})
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length) if content_length > 0 else b""
                try:
                    payload = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    self._write(400, {"accepted": False, "error": "invalid json"})
                    return

                if not isinstance(payload, dict):
                    self._write(400, {"accepted": False, "error": "json body must be an object"})
                    return

                status, response = on_track(payload)
                self._write(status, response)

            def do_GET(self) -> None:
                if self.path == "/health":
                    self._write(200, {"status": "ok"})
                    return
                self._write(404, {"error": "not found"})

            def _write(self, status: int, payload: Dict[str, object]) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, fmt: str, *args) -> None:
                return

        return Handler

