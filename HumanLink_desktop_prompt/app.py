from __future__ import annotations

import argparse
import signal
import sys

from PySide6.QtWidgets import QApplication

from humanlink_desktop_prompt.coordinator import TrackingCoordinator
from humanlink_desktop_prompt.ingress import IngressServer
from humanlink_desktop_prompt.tracker import TrackerConfig
from humanlink_desktop_prompt.ui import TrayApplication


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HumanLink Desktop Prompt")
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8989)
    parser.add_argument("--sdk-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--poll-interval-ms", type=int, default=500)
    parser.add_argument("--session-timeout-seconds", type=float, default=45.0)
    parser.add_argument("--auto-hide-ms", type=int, default=5000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    qt_app = QApplication(sys.argv)
    tray_app = TrayApplication(qt_app, auto_hide_ms=args.auto_hide_ms)

    tracker_config = TrackerConfig(
        sdk_base_url=args.sdk_base_url,
        poll_interval_seconds=max(0.1, args.poll_interval_ms / 1000.0),
        session_timeout_seconds=max(1.0, args.session_timeout_seconds),
    )
    coordinator = TrackingCoordinator(tracker_config=tracker_config, event_sink=tray_app.emit_event)
    ingress = IngressServer(args.listen_host, args.listen_port, coordinator.handle_track)
    ingress.start()

    print(
        f"HumanLink Desktop Prompt running at http://{args.listen_host}:{ingress.bound_port}, "
        f"sdk={args.sdk_base_url}"
    )

    def shutdown(*_: object) -> None:
        coordinator.stop_all()
        ingress.stop()
        qt_app.quit()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    qt_app.aboutToQuit.connect(lambda: (coordinator.stop_all(), ingress.stop()))

    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

