from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from sdk.assertion.schema import validate_assertion_structure
from sdk.crypto.ecdsa_verify import SignatureVerificationUnavailable, verify_assertion_signature
from sdk.crypto.hash_engine import build_action_hash, compute_h_doc, rebuild_signed_hash
from sdk.db.store import SQLiteStore
from sdk.device_registry import DeviceRegistry
from sdk.identity.did_resolver import build_did_document, decode_did_key
from sdk.trust_policy import TrustPolicy, evaluate_attestation
from sdk.types import Challenge, Config, VerificationResult, isoformat_z, utc_now


DEFAULT_CONFIG = {
    "hardware": {"serial_port": None, "usb_baud": 115200},
    "protocol": {"version": "0.3"},
    "verification": {
        "chain_check": "skip",
        "max_age_seconds": 30,
        "min_match_score": 100,
        "trust_policy": "default",
        "enforce_device_binding": True,
    },
    "gateway": {"mode": "local"},
    "api": {"host": "127.0.0.1", "port": 8765},
    "device": {},
    "audit": {},
    "db": {"path": "~/.humanlink/humanlink.db"},
}


class HumanLinkVerifier:
    def __init__(self, config_path: str):
        self.config_path = os.path.expanduser(config_path)
        self.config = self._load_config(self.config_path)
        self.store = SQLiteStore(self.config.db["path"])
        self.device_registry = DeviceRegistry(self.store, self.config.device.get("did"))

    def _load_config(self, path: str) -> Config:
        raw = {}
        if Path(path).exists():
            with open(path, "r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
        merged = {}
        for key, default_value in DEFAULT_CONFIG.items():
            current = dict(default_value)
            current.update(raw.get(key, {}))
            merged[key] = current
        return Config(**merged)

    def get_required_issuer_did(self, user_id: Optional[str] = None) -> str:
        return self.device_registry.get_required_issuer_did(user_id)

    def create_challenge(
        self,
        action: str,
        action_params: dict,
        display_title: str,
        display_summary: str,
        risk: str,
        origin: str = "local://openclaw",
    ) -> dict:
        required_issuer_did = self.get_required_issuer_did()
        nonce = secrets.token_hex(8)
        action_hash = build_action_hash(
            action=action,
            params=action_params,
            nonce=nonce,
            required_issuer_did=required_issuer_did,
        )
        challenge = Challenge(
            origin=origin,
            action=action,
            requiredIssuerDID=required_issuer_did,
            actionHash=action_hash,
            nonce=nonce,
            issuedAt=isoformat_z(utc_now()),
            display={
                "title": display_title[:64],
                "summary": display_summary[:256],
                "risk": risk,
                "source": origin,
            },
            params=dict(action_params),
        )
        return challenge.to_dict()

    def get_device_did_document(self) -> Dict[str, object]:
        return build_did_document(self.get_required_issuer_did())

    def get_device_attestation(self) -> Dict[str, Any]:
        return {
            "sensorType": "optical_fingerprint",
            "sensorFAR": 0.00001,
            "sensorFRR": 0.01,
            "secureElement": "ATECC608A",
            "livenessDetection": False,
        }

    def _failure(self, step: int, reason: str, assertion: Dict[str, Any]) -> VerificationResult:
        return VerificationResult(
            valid=False,
            failure_step=step,
            failure_reason=reason,
            device_did=assertion.get("device", {}).get("id", ""),
            assertion_id=assertion.get("id", ""),
            chain_checked=False,
            chain_check_reason="skipped_config",
            verified_at=utc_now(),
        )

    def verify(self, assertion: dict, challenge: dict) -> VerificationResult:
        if not validate_assertion_structure(assertion):
            return self._failure(1, "INVALID_STRUCTURE", assertion)

        if assertion["device"]["id"] != challenge["requiredIssuerDID"] or assertion["proof"]["verificationMethod"] != f"{challenge['requiredIssuerDID']}#key-0":
            return self._failure(2, "DEVICE_BINDING_MISMATCH", assertion)

        expected_action_hash = build_action_hash(
            action=challenge["action"],
            params=challenge.get("params", {}),
            nonce=challenge["nonce"],
            required_issuer_did=challenge["requiredIssuerDID"],
        )
        if assertion["challenge"]["actionHash"] != expected_action_hash:
            return self._failure(3, "ACTION_HASH_MISMATCH", assertion)

        if assertion["challenge"]["origin"] != challenge["origin"]:
            return self._failure(4, "ORIGIN_MISMATCH", assertion)

        device_did = assertion["device"]["id"]
        nonce = challenge["nonce"]
        if self.store.nonce_exists(device_did, nonce):
            return self._failure(5, "NONCE_REPLAY", assertion)

        try:
            created = datetime.fromisoformat(assertion["created"].replace("Z", "+00:00"))
        except ValueError:
            return self._failure(6, "INVALID_TIMESTAMP", assertion)
        age_seconds = (utc_now() - created.astimezone(timezone.utc)).total_seconds()
        max_age = int(self.config.verification["max_age_seconds"])
        if age_seconds < 0:
            return self._failure(6, "FUTURE_TIMESTAMP", assertion)
        if age_seconds > max_age:
            return self._failure(6, "EXPIRED", assertion)

        if int(assertion["evidence"]["matchScore"]) < int(self.config.verification["min_match_score"]):
            return self._failure(7, "SCORE_TOO_LOW", assertion)

        if not evaluate_attestation(assertion["device"]["attestation"], self.config.verification["trust_policy"]):
            return self._failure(8, "ATTESTATION_POLICY_FAILED", assertion)

        skeleton = dict(assertion)
        proof = skeleton.pop("proof")
        h_doc = compute_h_doc(skeleton)
        try:
            rebuilt_signed_hash = rebuild_signed_hash(
                matched_id=int(assertion["subject"]["localId"].replace("slot-", "")),
                score=int(assertion["evidence"]["matchScore"]),
                sensor_serial=bytes.fromhex(assertion["evidence"]["sensorSerial"]),
                nonce=bytes.fromhex(assertion["challenge"]["nonce"]),
                h_doc=h_doc,
            )
        except (ValueError, TypeError):
            return self._failure(9, "SIGNED_HASH_MALFORMED", assertion)

        if proof["signedHash"] != rebuilt_signed_hash.hex():
            return self._failure(9, "SIGNED_HASH_MISMATCH", assertion)

        try:
            pubkey_bytes = decode_did_key(proof["verificationMethod"])
            if not verify_assertion_signature(pubkey_bytes, rebuilt_signed_hash, proof["signature"]):
                return self._failure(9, "SIGNATURE_INVALID", assertion)
        except SignatureVerificationUnavailable:
            return self._failure(9, "SIGNATURE_VERIFICATION_UNAVAILABLE", assertion)
        except Exception:
            return self._failure(9, "SIGNATURE_INVALID", assertion)

        self.store.record_nonce(device_did, nonce, assertion["created"])
        return VerificationResult(
            valid=True,
            failure_step=None,
            failure_reason=None,
            device_did=device_did,
            assertion_id=assertion["id"],
            chain_checked=False,
            chain_check_reason="skipped_config",
            verified_at=utc_now(),
        )
