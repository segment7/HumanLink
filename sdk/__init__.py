"""
HumanLink SDK

Python SDK for HumanLink Protocol v0.3
"""

from .client import HumanLinkClient
from .verifier import HumanLinkVerifier
from .data_types import (
    HumanPresenceAssertion, Challenge, VerifyResult, AuthResult,
    DeviceStatus, TrustPolicy, RiskLevel
)

__version__ = "0.3.0"
__all__ = [
    'HumanLinkClient',
    'HumanLinkVerifier',
    'HumanPresenceAssertion',
    'Challenge',
    'VerifyResult',
    'AuthResult',
    'DeviceStatus',
    'TrustPolicy',
    'RiskLevel'
]