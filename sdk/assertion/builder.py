"""
Assertion Builder for HumanLink Protocol

Handles assembly, canonicalization, and signature injection for HumanPresenceAssertion
"""
import uuid
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from data_types import (
    HumanPresenceAssertion, Device, DeviceAttestation, Subject,
    Challenge, DisplayInfo, Evidence, Proof, AuthResult
)
from crypto import HashEngine


class AssertionBuilder:
    """Builds and assembles HumanPresenceAssertion objects"""

    def __init__(self):
        pass

    def build_skeleton(self, challenge: Challenge, device_did: str,
                      device_attestation: DeviceAttestation) -> HumanPresenceAssertion:
        """
        Build assertion skeleton (without proof)

        Args:
            challenge: Challenge object
            device_did: Device DID
            device_attestation: Device hardware attestation

        Returns:
            HumanPresenceAssertion without proof field
        """
        # Generate unique ID
        assertion_id = f"urn:uuid:{uuid.uuid4()}"

        # Current timestamp
        created = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Build device info
        device = Device(
            id=device_did,
            attestation=device_attestation
        )

        # Placeholder subject (will be filled after device response)
        subject = Subject(
            local_id="unknown",
            is_registered=True
        )

        # Placeholder evidence (will be filled after device response)
        evidence = Evidence(
            match_score=0,
            sensor_serial=""
        )

        return HumanPresenceAssertion(
            id=assertion_id,
            created=created,
            device=device,
            subject=subject,
            challenge=challenge,
            evidence=evidence,
            proof=None  # Will be added later
        )

    def inject_auth_result(self, assertion: HumanPresenceAssertion,
                          auth_result: AuthResult) -> HumanPresenceAssertion:
        """
        Inject authentication result into assertion

        Args:
            assertion: Assertion skeleton
            auth_result: Result from device authentication

        Returns:
            Updated assertion with evidence and proof
        """
        # Update subject with actual match info
        assertion.subject.local_id = f"slot-{auth_result.matched_id:02d}"
        assertion.subject.is_registered = True

        # Update evidence
        assertion.evidence.match_score = auth_result.score
        assertion.evidence.sensor_serial = auth_result.sensor_serial

        # Create proof object
        verification_method = f"{assertion.device.id}#key-0"

        proof = Proof(
            type="ECDSA-P256",
            signed_hash=auth_result.signed_hash,
            signature=auth_result.signature,
            verification_method=verification_method
        )

        assertion.proof = proof
        return assertion

    def build_challenge(self, action: str, action_params: Dict[str, Any],
                       required_issuer_did: str, origin: str,
                       display_title: str, display_summary: str,
                       risk: str = "high") -> Challenge:
        """
        Build challenge object

        Args:
            action: Action type
            action_params: Action parameters
            required_issuer_did: Required device DID
            origin: Request origin
            display_title: Display title for user
            display_summary: Display summary for user
            risk: Risk level

        Returns:
            Challenge object
        """
        # Generate nonce
        nonce = uuid.uuid4().hex[:16]

        # Compute action hash
        action_hash = HashEngine.compute_action_hash(
            action, action_params, nonce, required_issuer_did
        )

        # Current timestamp
        issued_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

        # Build display info
        display = DisplayInfo(
            title=display_title,
            summary=display_summary,
            risk=risk,
            source=origin
        )

        return Challenge(
            origin=origin,
            action=action,
            required_issuer_did=required_issuer_did,
            action_hash=action_hash,
            nonce=nonce,
            issued_at=issued_at,
            display=display
        )

    def canonicalize_skeleton(self, assertion: HumanPresenceAssertion) -> Dict[str, Any]:
        """
        Canonicalize assertion skeleton for h_doc computation

        Args:
            assertion: Assertion object

        Returns:
            Canonicalized dictionary (without proof)
        """
        return assertion.skeleton_dict()

    def compute_h_doc(self, assertion: HumanPresenceAssertion) -> str:
        """
        Compute h_doc for assertion skeleton

        Args:
            assertion: Assertion object

        Returns:
            64-character hex hash
        """
        skeleton = self.canonicalize_skeleton(assertion)
        return HashEngine.compute_h_doc_hex(skeleton)

    def validate_assertion(self, assertion: HumanPresenceAssertion) -> bool:
        """
        Validate assertion structure

        Args:
            assertion: Assertion to validate

        Returns:
            True if valid
        """
        # Check required fields
        if not assertion.id or not assertion.created:
            return False

        if not assertion.device.id or not assertion.challenge:
            return False

        # Check DID consistency
        if assertion.device.id != assertion.challenge.required_issuer_did:
            return False

        # Check proof if present
        if assertion.proof:
            expected_verification_method = f"{assertion.device.id}#key-0"
            if assertion.proof.verification_method != expected_verification_method:
                return False

        return True

    def create_complete_assertion(self, action: str, action_params: Dict[str, Any],
                                 device_did: str, device_attestation: DeviceAttestation,
                                 origin: str, display_title: str, display_summary: str,
                                 auth_result: AuthResult, risk: str = "high") -> HumanPresenceAssertion:
        """
        Create complete assertion from inputs

        Args:
            action: Action type
            action_params: Action parameters
            device_did: Device DID
            device_attestation: Device attestation
            origin: Request origin
            display_title: Display title
            display_summary: Display summary
            auth_result: Authentication result from device
            risk: Risk level

        Returns:
            Complete HumanPresenceAssertion
        """
        # Build challenge
        challenge = self.build_challenge(
            action, action_params, device_did, origin,
            display_title, display_summary, risk
        )

        # Build skeleton
        assertion = self.build_skeleton(challenge, device_did, device_attestation)

        # Inject auth result
        assertion = self.inject_auth_result(assertion, auth_result)

        return assertion

    def assertion_to_json(self, assertion: HumanPresenceAssertion) -> str:
        """
        Convert assertion to JSON string

        Args:
            assertion: Assertion object

        Returns:
            JSON string
        """
        import json
        return json.dumps(assertion.to_dict(), indent=2)

    def assertion_from_dict(self, data: Dict[str, Any]) -> HumanPresenceAssertion:
        """
        Create assertion from dictionary

        Args:
            data: Assertion dictionary

        Returns:
            HumanPresenceAssertion object
        """
        # Build device
        device_data = data["device"]
        device = Device(
            id=device_data["id"],
            attestation=DeviceAttestation(**device_data["attestation"])
        )

        # Build subject
        subject_data = data["subject"]
        subject = Subject(
            local_id=subject_data["localId"],
            is_registered=subject_data["isRegistered"]
        )

        # Build challenge
        challenge_data = data["challenge"]
        display_data = challenge_data["display"]

        display = DisplayInfo(
            title=display_data["title"],
            summary=display_data["summary"],
            risk=display_data["risk"],
            source=display_data["source"]
        )

        challenge = Challenge(
            origin=challenge_data["origin"],
            action=challenge_data["action"],
            required_issuer_did=challenge_data["requiredIssuerDID"],
            action_hash=challenge_data["actionHash"],
            nonce=challenge_data["nonce"],
            issued_at=challenge_data["issuedAt"],
            display=display
        )

        # Build evidence
        evidence_data = data["evidence"]
        evidence = Evidence(
            match_score=evidence_data["matchScore"],
            sensor_serial=evidence_data["sensorSerial"]
        )

        # Build proof (if present)
        proof = None
        if "proof" in data:
            proof_data = data["proof"]
            proof = Proof(
                type=proof_data["type"],
                signed_hash=proof_data["signedHash"],
                signature=proof_data["signature"],
                verification_method=proof_data["verificationMethod"]
            )

        return HumanPresenceAssertion(
            context=data.get("@context", "https://humanlink.dev/protocol/v0-3"),
            type=data.get("type", "HumanPresenceAssertion"),
            id=data["id"],
            version=data.get("version", "0.3"),
            created=data["created"],
            device=device,
            subject=subject,
            challenge=challenge,
            evidence=evidence,
            proof=proof
        )