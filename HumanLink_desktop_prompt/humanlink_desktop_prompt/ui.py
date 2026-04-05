from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMenu,
    QProgressBar,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .types import PromptEvent, PromptStage


class EventBridge(QObject):
    event_signal = Signal(object)


class PromptWindow(QWidget):
    def __init__(self, auto_hide_ms: int = 5000) -> None:
        super().__init__()
        self.auto_hide_ms = auto_hide_ms
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("HumanLink 认证提示")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        self.stage_label = QLabel("等待认证事件...")
        self.stage_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.stage_label)

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.session_label = QLabel("")
        layout.addWidget(self.session_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)

        layout.addWidget(QLabel("历史记录（最新在上）："))
        self.history = QListWidget()
        layout.addWidget(self.history)

        self.hide_btn = QPushButton("隐藏")
        self.hide_btn.clicked.connect(self.hide)
        layout.addWidget(self.hide_btn)

    def on_event(self, event: PromptEvent) -> None:
        self.stage_label.setText(f"当前步骤：{event.stage.value}")
        self.message_label.setText(event.message)
        self.session_label.setText(f"session: {event.session_id} | tracking: {event.tracking_id}")

        if event.progress is None:
            self.progress.hide()
        else:
            self.progress.setValue(max(0, min(100, event.progress)))
            self.progress.show()

        line = f"[{event.timestamp}] {event.session_id} {event.message}"
        self.history.insertItem(0, line)
        self.history.setCurrentRow(0)

        self.show()
        self.raise_()
        self.activateWindow()

        if event.stage in {PromptStage.SUCCESS, PromptStage.FAILED, PromptStage.TIMEOUT}:
            QTimer.singleShot(self.auto_hide_ms, self.hide)


class TrayApplication:
    def __init__(self, app: QApplication, auto_hide_ms: int = 5000) -> None:
        self.app = app
        self.bridge = EventBridge()
        self.window = PromptWindow(auto_hide_ms=auto_hide_ms)
        self.bridge.event_signal.connect(self.window.on_event)
        self.tray = self._create_tray()

    def _create_tray(self) -> QSystemTrayIcon:
        icon: Optional[QIcon] = self.app.style().standardIcon(QStyle.SP_MessageBoxInformation)
        tray = QSystemTrayIcon(icon, self.app)
        tray.setToolTip("HumanLink Desktop Prompt")
        menu = QMenu()

        open_action = QAction("打开提示窗口", self.app)
        open_action.triggered.connect(self.window.show)
        menu.addAction(open_action)

        quit_action = QAction("退出", self.app)
        quit_action.triggered.connect(self.app.quit)
        menu.addAction(quit_action)

        tray.setContextMenu(menu)
        tray.show()
        return tray

    def emit_event(self, event: PromptEvent) -> None:
        self.bridge.event_signal.emit(event)

