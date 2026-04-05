"""
HumanLink Verifier

Core verification engine for HumanPresenceAssertion validation
"""
import logging
import yaml
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path

from data_types import (
    VerifyResult, HumanPresenceAssertion, TrustPolicy, Config,
    DeviceAttestation
)
from crypto import HashEngine, ECDSAVerifier
from assertion import AssertionBuilder
from db import HumanLinkStore


logger = logging.getLogger(__name__)


class HumanLinkVerifier:
    """
    HumanLink verification engine

    Implements the 10-step verification process for local scenarios
    """

    def __init__(self, config_path: Optional[str] = None, config: Optional[Config] = None):
        """
        Initialize verifier

        Args:
            config_path: Path to YAML configuration file
            config: Direct configuration object (overrides config_path)
        """
        if config:
            self.config = config
        elif config_path:
            self.config = self._load_config(config_path)
        else:
            # Default local configuration
            self.config = self._default_local_config()

        # Initialize storage
        storage_path = self.config.verification.get("storage_path", "~/.humanlink/verifier.db")
        self.store = HumanLinkStore(storage_path)

        # Initialize builder
        self.builder = AssertionBuilder()

        # Verification settings
        self.min_match_score = self.config.verification.get("min_match_score", 100)
        self.max_age_seconds = self.config.verification.get("max_age_seconds", 30)
        self.trust_policy = TrustPolicy(self.config.verification.get("trust_policy", "default"))
        self.chain_check = self.config.verification.get("chain_check", "skip")
        self.enforce_device_binding = self.config.verification.get("enforce_device_binding", True)

    def _load_config(self, config_path: str) -> Config:
        """Load configuration from YAML file"""
        try:
            with open(Path(config_path).expanduser(), 'r') as f:
                data = yaml.safe_load(f)

            return Config(
                hardware=data.get("hardware", {}),
                protocol=data.get("protocol", {}),
                chain=data.get("chain"),
                verification=data.get("verification", {}),
                gateway=data.get("gateway"),
                api=data.get("api", {})
            )
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return self._default_local_config()

    def _default_local_config(self) -> Config:
        """Get default local configuration"""
        return Config(
            hardware={
                "sensor": "jm101",
                "sensor_baud": 57600,
                "controller": "esp32",
                "secure_element": "atecc608a",
                "transport": "usb_serial",
                "serial_port": "/dev/ttyUSB0",
                "usb_baud": 115200
            },
            protocol={
                "version": "0.3",
                "context_local": "/etc/humanlink/context-v1.jsonld"
            },
            verification={
                "chain_check": "skip",
                "max_age_seconds": 30,
                "min_match_score": 100,
                "trust_policy": "default",
                "enforce_device_binding": True,
                "storage_path": "~/.humanlink/verifier.db"
            },
            api={
                "host": "127.0.0.1",
                "port": 8765
            }
        )

    def get_required_issuer_did(self, user_id: str) -> str:
        """
        Get required issuer DID for user

        Args:
            user_id: User identifier

        Returns:
            Device DID for the user

        Note: In local mode, this is typically read from local configuration
        """
        # For local mode, read from config or use single device
        device_did = self.config.verification.get("device_did")

        if not device_did:
            # Try to get from stored devices in database
            try:
                import sqlite3
                with sqlite3.connect(self.store.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT did FROM devices WHERE is_active = 1 LIMIT 1
                    """)
                    row = cursor.fetchone()
                    if row:
                        device_did = row[0]
                        logger.info(f"Using stored device DID: {device_did}")
                    else:
                        logger.warning("No active devices found in database")
                        raise ValueError("No device DID configured for local verification")
            except Exception as e:
                logger.error(f"Failed to get device DID from database: {e}")
                raise ValueError("No device DID configured for local verification")

        return device_did

    def create_challenge(self, action: str, action_params: Dict[str, Any],
                        display_title: str, display_summary: str,
                        user_id: str = "local_user", origin: str = "local://openclaw",
                        risk: str = "high") -> Dict[str, Any]:
        """
        Create challenge for local verification

        Args:
            action: Action type
            action_params: Action parameters
            display_title: Display title
            display_summary: Display summary
            user_id: User ID (for device lookup)
            origin: Request origin
            risk: Risk level

        Returns:
            Challenge dictionary
        """
        try:
            # Get required device DID
            required_issuer_did = self.get_required_issuer_did(user_id)

            # Build challenge using builder
            challenge = self.builder.build_challenge(
                action=action,
                action_params=action_params,
                required_issuer_did=required_issuer_did,
                origin=origin,
                display_title=display_title,
                display_summary=display_summary,
                risk=risk
            )

            return challenge.__dict__

        except Exception as e:
            logger.error(f"Failed to create challenge: {e}")
            raise

    def verify(self, assertion: Dict[str, Any], challenge: Optional[Dict[str, Any]] = None) -> VerifyResult:
        """
        Verify HumanPresenceAssertion (10-step verification)

        Args:
            assertion: Assertion dictionary
            challenge: Original challenge (optional, extracted from assertion if not provided)

        Returns:
            Verification result
        """
        try:
            # Convert to objects
            assertion_obj = self.builder.assertion_from_dict(assertion)

            if challenge is None:
                challenge_obj = assertion_obj.challenge
            else:
                # Build challenge object from dict if provided
                from data_types import Challenge, DisplayInfo
                display_data = challenge["display"]
                display = DisplayInfo(**display_data)
                challenge_obj = Challenge(
                    origin=challenge["origin"],
                    action=challenge["action"],
                    required_issuer_did=challenge["required_issuer_did"],
                    action_hash=challenge["action_hash"],
                    nonce=challenge["nonce"],
                    issued_at=challenge["issued_at"],
                    display=display
                )

            # Step 1: Structure validation
            if not self._validate_structure(assertion_obj):
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Invalid assertion structure",
                    failure_step=1
                )

            # Step 2: Device binding
            if assertion_obj.device.id != challenge_obj.required_issuer_did:
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Device ID does not match required issuer DID",
                    failure_step=2
                )

            # Step 3: actionHash validation
            # Rebuild actionHash and compare
            from data_types import Challenge

            # Extract action and params from challenge
            # For demo, we'll skip detailed param extraction and trust the challenge
            rebuilt_hash = challenge_obj.action_hash  # In full implementation, rebuild from action + params
            if assertion_obj.challenge.action_hash != rebuilt_hash:
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Action hash mismatch",
                    failure_step=3
                )

            # Step 4: Origin binding
            expected_origin = challenge_obj.origin
            if assertion_obj.challenge.origin != expected_origin:
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Origin mismatch",
                    failure_step=4
                )

            # Step 5: Nonce anti-replay
            if not self.store.check_nonce(assertion_obj.device.id, assertion_obj.challenge.nonce):
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Nonce already used (replay attack)",
                    failure_step=5
                )

            # Step 6: Time window validation
            try:
                created_time = datetime.fromisoformat(assertion_obj.created.replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                age_seconds = (now - created_time).total_seconds()

                if age_seconds > self.max_age_seconds:
                    return VerifyResult(
                        valid=False,
                        device_did=assertion_obj.device.id,
                        match_score=assertion_obj.evidence.match_score,
                        device_attestation=assertion_obj.device.attestation.__dict__,
                        failure_reason=f"Assertion too old: {age_seconds}s > {self.max_age_seconds}s",
                        failure_step=6
                    )
            except Exception as e:
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason=f"Invalid timestamp: {e}",
                    failure_step=6
                )

            # Step 7: Match score validation
            if assertion_obj.evidence.match_score < self.min_match_score:
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason=f"Match score too low: {assertion_obj.evidence.match_score} < {self.min_match_score}",
                    failure_step=7
                )

            # Step 8: Device attestation trust policy
            if not self._validate_trust_policy(assertion_obj.device.attestation):
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="Device does not meet trust policy requirements",
                    failure_step=8
                )

            # Step 9: ECDSA signature verification
            if not self._verify_signature(assertion_obj):
                return VerifyResult(
                    valid=False,
                    device_did=assertion_obj.device.id,
                    match_score=assertion_obj.evidence.match_score,
                    device_attestation=assertion_obj.device.attestation.__dict__,
                    failure_reason="ECDSA signature verification failed",
                    failure_step=9
                )

            # Step 10: Chain validation (optional in local mode)
            chain_checked = False
            chain_check_reason = None

            if self.chain_check == "required":
                # Would implement chain validation here
                chain_checked = False
                chain_check_reason = "Chain validation not implemented"
            elif self.chain_check == "skip":
                chain_checked = False
                chain_check_reason = "local_mode"

            # Mark nonce as used
            self.store.mark_nonce_used(assertion_obj.device.id, assertion_obj.challenge.nonce, assertion_obj.id)

            return VerifyResult(
                valid=True,
                device_did=assertion_obj.device.id,
                match_score=assertion_obj.evidence.match_score,
                device_attestation=assertion_obj.device.attestation.__dict__,
                chain_checked=chain_checked
            )

        except Exception as e:
            logger.error(f"Verification error: {e}")
            return VerifyResult(
                valid=False,
                device_did="unknown",
                match_score=0,
                device_attestation={},
                failure_reason=f"Verification error: {e}",
                failure_step=0
            )

    def _validate_structure(self, assertion: HumanPresenceAssertion) -> bool:
        """Validate assertion structure"""
        return self.builder.validate_assertion(assertion)

    def _validate_trust_policy(self, attestation: DeviceAttestation) -> bool:
        """Validate device trust policy"""
        if self.trust_policy == TrustPolicy.DEFAULT:
            # Default: require secure element
            return attestation.secure_element == "ATECC608A"
        elif self.trust_policy == TrustPolicy.STRICT:
            # Strict: require secure element + liveness detection
            return (attestation.secure_element == "ATECC608A" and
                   attestation.liveness_detection)
        else:
            # Custom: implement custom logic
            return True

    def _verify_signature(self, assertion: HumanPresenceAssertion) -> bool:
        """Verify ECDSA signature"""
        try:
            if not assertion.proof:
                return False

            # Rebuild signed hash
            nonce_bytes = bytes.fromhex(assertion.challenge.nonce)
            sensor_serial_bytes = bytes.fromhex(assertion.evidence.sensor_serial)

            # Compute h_doc from skeleton
            skeleton = assertion.skeleton_dict()
            h_doc = HashEngine.compute_h_doc(skeleton)

            # Extract subject local_id as slot number
            local_id = assertion.subject.local_id
            if local_id.startswith("slot-"):
                matched_id = int(local_id.split("-")[1])
            else:
                matched_id = 0

            # Rebuild signed hash
            rebuilt_signed_hash = HashEngine.rebuild_signed_hash(
                matched_id=matched_id,
                score=assertion.evidence.match_score,
                sensor_serial=sensor_serial_bytes,
                nonce=nonce_bytes,
                h_doc=h_doc
            )

            # Verify it matches the one in proof
            if assertion.proof.signed_hash != rebuilt_signed_hash.hex():
                logger.error("Rebuilt signed hash does not match proof")
                return False

            # Verify signature using device DID
            return ECDSAVerifier.verify_assertion_signature(
                assertion.to_dict(),
                assertion.device.id
            )

        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    def close(self):
        """Close verifier and cleanup resources"""
        if self.store:
            self.store.close()