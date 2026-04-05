from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .types import PromptStage


def map_sdk_status(payload: Dict[str, Any]) -> Tuple[PromptStage, str, Optional[int], Optional[int], bool]:
    status = str(payload.get("status", "")).lower()
    device_status = str(payload.get("device_status", "")).lower()
    verification_progress = _as_int(payload.get("verification_progress"))
    verification_step = _as_int(payload.get("verification_step"))

    if status == "completed":
        return PromptStage.SUCCESS, "认证成功", 100, verification_step, True

    if status == "failed":
        error = str(payload.get("error") or "").strip()
        if error:
            return PromptStage.FAILED, f"认证失败：{error}", verification_progress, verification_step, True
        return PromptStage.FAILED, "认证失败", verification_progress, verification_step, True

    if device_status in {"processing", "verifying"} or verification_step is not None or verification_progress is not None:
        progress = verification_progress if verification_progress is not None else 0
        return PromptStage.VERIFYING_SIGNATURE, "已采集指纹，正在校验签名", progress, verification_step, False

    if device_status in {"waiting_for_biometric", "retry_needed"}:
        return PromptStage.WAITING_THUMB, "请按压拇指进行授权", None, verification_step, False

    if device_status in {"connecting", "computing"}:
        return PromptStage.CONNECTING_DEVICE, "正在连接设备", None, verification_step, False

    return PromptStage.CHALLENGE_CREATED, "正在发起认证 / challenge 已生成", None, verification_step, False


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        parsed = int(str(value))
        return parsed
    except (ValueError, TypeError):
        return None

