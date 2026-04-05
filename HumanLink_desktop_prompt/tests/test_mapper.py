from humanlink_desktop_prompt.mapper import map_sdk_status
from humanlink_desktop_prompt.types import PromptStage


def test_map_waiting_thumb():
    stage, msg, progress, step, terminal = map_sdk_status(
        {"status": "authenticating", "device_status": "waiting_for_biometric"}
    )
    assert stage == PromptStage.WAITING_THUMB
    assert "拇指" in msg
    assert progress is None
    assert step is None
    assert terminal is False


def test_map_verifying_by_progress():
    stage, msg, progress, step, terminal = map_sdk_status(
        {"status": "authenticating", "verification_progress": 30, "verification_step": 3}
    )
    assert stage == PromptStage.VERIFYING_SIGNATURE
    assert progress == 30
    assert step == 3
    assert terminal is False


def test_map_success():
    stage, msg, progress, _, terminal = map_sdk_status({"status": "completed"})
    assert stage == PromptStage.SUCCESS
    assert msg == "认证成功"
    assert progress == 100
    assert terminal is True

