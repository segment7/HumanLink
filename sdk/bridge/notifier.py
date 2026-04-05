"""
HumanLink System Notifier

Native OS notifications for biometric authorization prompts.
macOS: osascript  |  Linux: notify-send  |  Windows: toast
"""
import subprocess
import platform
import logging

logger = logging.getLogger(__name__)

_SYSTEM = platform.system()


def notify(title: str, message: str, sound: bool = True) -> None:
    """Send a native OS notification."""
    try:
        if _SYSTEM == "Darwin":
            _notify_macos(title, message, sound)
        elif _SYSTEM == "Linux":
            _notify_linux(title, message)
        elif _SYSTEM == "Windows":
            _notify_windows(title, message)
        else:
            logger.warning(f"Unsupported platform for notifications: {_SYSTEM}")
    except Exception as e:
        logger.debug(f"Notification failed (non-critical): {e}")


def _notify_macos(title: str, message: str, sound: bool) -> None:
    sound_part = 'sound name "Funk"' if sound else ""
    script = f'display notification "{message}" with title "{title}" {sound_part}'
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)


def _notify_linux(title: str, message: str) -> None:
    subprocess.run(["notify-send", title, message], capture_output=True, timeout=5)


def _notify_windows(title: str, message: str) -> None:
    # PowerShell toast notification
    ps_script = (
        f'[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, '
        f'ContentType = WindowsRuntime] > $null; '
        f'$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(0); '
        f'$text = $template.GetElementsByTagName("text"); '
        f'$text[0].AppendChild($template.CreateTextNode("{title}")) > $null; '
        f'$text[1].AppendChild($template.CreateTextNode("{message}")) > $null; '
        f'$toast = [Windows.UI.Notifications.ToastNotification]::new($template); '
        f'[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("HumanLink").Show($toast)'
    )
    subprocess.run(["powershell", "-Command", ps_script], capture_output=True, timeout=5)
