"""
HumanLink SDK Type Definitions

Type definitions for the HumanLink Protocol v0.3
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


class TrustPolicy(Enum):
    """Device trust policy levels"""
    DEFAULT = "default"
    STRICT = "strict"
    CUSTOM = "custom"


class RiskLevel(Enum):
    """Operation risk levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DeviceAttestation:
    """Device hardware attestation information"""
    sensor_type: str = "optical_fingerprint"
    sensor_far: float = 0.00001  # False Accept Rate
    sensor_frr: float = 0.01     # False Reject Rate
    secure_element: str = "ATECC608A"
    liveness_detection: bool = False


@dataclass
class Device:
    """Device information in assertion"""
    id: str  # did:key format
    attestation: DeviceAttestation


@dataclass
class Subject:
    """Subject (user) information"""
    local_id: str  # e.g., "slot-03"
    is_registered: bool = True


@dataclass
class DisplayInfo:
    """Display information for user confirmation"""
    title: str
    summary: str
    risk: str = "high"
    source: str = ""


@dataclass
class Challenge:
    """Challenge data structure"""
    origin: str
    action: str
    required_issuer_did: str
    action_hash: str
    nonce: str
    issued_at: str  # ISO 8601
    display: DisplayInfo


@dataclass
class Evidence:
    """Biometric evidence"""
    match_score: int
    sensor_serial: str


@dataclass
class Proof:
    """Cryptographic proof"""
    signed_hash: str
    signature: str
    verification_method: str
    type: str = "ECDSA-P256"


@dataclass
class HumanPresenceAssertion:
    """Complete HumanPresenceAssertion structure"""
    id: str
    created: str  # ISO 8601
    device: Device
    subject: Subject
    challenge: Challenge
    evidence: Evidence
    context: str = "https://humanlink.dev/protocol/v0-3"
    type: str = "HumanPresenceAssertion"
    version: str = "0.3"
    proof: Optional[Proof] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        result = {
            "@context": self.context,
            "type": self.type,
            "id": self.id,
            "version": self.version,
            "created": self.created,
            "device": asdict(self.device),
            "subject": asdict(self.subject),
            "challenge": asdict(self.challenge),
            "evidence": asdict(self.evidence)
        }
        if self.proof:
            result["proof"] = asdict(self.proof)
        return result

    def skeleton_dict(self) -> Dict[str, Any]:
        """Get skeleton (without proof) for h_doc calculation"""
        result = self.to_dict()
        if "proof" in result:
            del result["proof"]
        return result


@dataclass
class AuthResult:
    """Authentication result from device"""
    matched_id: int
    score: int
    sensor_serial: str
    signature: str
    public_key: str
    signed_hash: str
    nonce: str


@dataclass
class VerifyResult:
    """Verification result"""
    valid: bool
    device_did: str
    match_score: int
    device_attestation: Dict[str, Any]
    chain_checked: bool = False
    failure_reason: Optional[str] = None
    failure_step: Optional[int] = None


@dataclass
class Config:
    """HumanLink configuration"""
    # Hardware settings
    hardware: Dict[str, Any]

    # Protocol settings
    protocol: Dict[str, str]

    # Chain settings (optional for local mode)
    chain: Optional[Dict[str, str]] = None

    # Verification settings
    verification: Dict[str, Any] = None

    # Gateway settings (for cloud mode)
    gateway: Optional[Dict[str, str]] = None

    # API settings
    api: Dict[str, Union[str, int]] = None


class ErrorCode:
    """Error codes matching firmware"""
    OK = 0
    ERR_BAD_INPUT = 1
    ERR_TIMEOUT = 2
    ERR_NO_MATCH = 3
    ERR_SENSOR = 4
    ERR_NOT_ENROLLED = 5


class DeviceState(Enum):
    """Device state enumeration"""
    INITIALIZING = "initializing"
    IDLE = "idle"
    AUTHORIZING = "authorizing"
    ENROLLING = "enrolling"


@dataclass
class DeviceStatus:
    """Device status information"""
    status: str
    state: DeviceState
    provisioned: bool
    enrolled: int
    protocol: str
    device_did: str
    needs_init: bool