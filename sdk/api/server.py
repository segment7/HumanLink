from __future__ import annotations

from typing import Any, Dict, Optional

from sdk.client import HumanLinkClient
from sdk.verifier import HumanLinkVerifier


def build_app(config_path: str, client: Optional[HumanLinkClient] = None):
    try:
        from fastapi import FastAPI, HTTPException
    except ModuleNotFoundError as exc:
        raise RuntimeError("fastapi is required to run the HumanLink API server") from exc

    verifier = HumanLinkVerifier(config_path=config_path)
    active_client = client or HumanLinkClient(
        port=verifier.config.hardware.get("serial_port"),
        baud=int(verifier.config.hardware.get("usb_baud", 115200)),
        attestation=verifier.get_device_attestation(),
    )

    app = FastAPI(title="HumanLink Local SDK", version="0.3")
    app.state.last_result = None

    @app.post("/auth/challenge")
    def auth_challenge(payload: Dict[str, Any]):
        required = ["action", "action_params", "display_title", "display_summary", "risk"]
        missing = [field for field in required if field not in payload]
        if missing:
            raise HTTPException(status_code=400, detail={"missing": missing})

        challenge = verifier.create_challenge(
            action=payload["action"],
            action_params=payload["action_params"],
            display_title=payload["display_title"],
            display_summary=payload["display_summary"],
            risk=payload["risk"],
            origin=payload.get("origin", "local://openclaw"),
        )
        assertion = active_client.request_auth(challenge=challenge, timeout_seconds=int(payload.get("timeout_seconds", 30)))
        result = verifier.verify(assertion=assertion, challenge=challenge)
        app.state.last_result = result.to_dict()
        return {"challenge": challenge, "assertion": assertion, "verification": result.to_dict()}

    @app.get("/auth/status")
    def auth_status():
        return {"last_result": app.state.last_result}

    @app.get("/device/did")
    def device_did():
        return verifier.get_device_did_document()

    @app.get("/device/attestation")
    def device_attestation():
        return verifier.get_device_attestation()

    return app
