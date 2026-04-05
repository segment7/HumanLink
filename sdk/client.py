"""
HumanLink USB Client

Main client interface for communicating with HumanLink devices
"""
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from data_types import (
    AuthResult, DeviceStatus, Challenge, HumanPresenceAssertion,
    DeviceAttestation
)
from hardware import USBBridge
from assertion import AssertionBuilder
from crypto import HashEngine
from db import HumanLinkStore


logger = logging.getLogger(__name__)


class HumanLinkClient:
    """
    HumanLink USB client for device communication

    Handles the complete flow from challenge generation to assertion creation
    """

    def __init__(self, port: Optional[str] = None, baud_rate: int = 115200,
                 timeout: float = 120.0, storage_path: Optional[str] = None):
        """
        Initialize HumanLink client

        Args:
            port: USB serial port (auto-detect if None)
            baud_rate: Serial baud rate
            timeout: Communication timeout
            storage_path: Path to local storage database
        """
        self.bridge = USBBridge(port, baud_rate, timeout)
        self.builder = AssertionBuilder()
        self.store = HumanLinkStore(storage_path) if storage_path else None
        self._device_did: Optional[str] = None
        self._device_attestation: Optional[DeviceAttestation] = None

        # Set up device monitoring
        self.bridge.add_device_callback(self._on_device_event)
        self.bridge.start_device_monitoring()

    def connect(self) -> bool:
        """
        Connect to HumanLink device

        Returns:
            True if connected successfully
        """
        try:
            success = self.bridge.connect()
        except Exception as e:
            logger.warning(f"Failed to connect to device: {e}")
            return False
        if success:
            try:
                logger.info("Getting device information...")

                # Get device info using DID command
                status = self.bridge.get_device_status()
                self._device_did = status.device_did

                if not self._device_did or self._device_did == "did:key:unknown":
                    logger.warning("Device DID not available")
                    # Still continue, might work for some operations

                # Get device attestation from status
                self._device_attestation = DeviceAttestation(
                    sensor_type="optical_fingerprint",
                    sensor_far=0.00001,
                    sensor_frr=0.01,
                    secure_element="ATECC608A",
                    liveness_detection=False
                )

                # Store device info if storage is available
                if self.store and self._device_did:
                    self.store.store_device(
                        self._device_did,
                        "",  # Public key will be extracted from first auth
                        self._device_attestation.__dict__
                    )

                logger.info(f"Connected to HumanLink device: {self._device_did}")
                logger.info(f"Device state: {status.state.value}, Enrolled: {status.enrolled} fingerprints")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize device info: {e}")
                self.disconnect()
                return False
        return False

    def disconnect(self):
        """Disconnect from device"""
        self.bridge.disconnect()
        self._device_did = None
        self._device_attestation = None

    def is_connected(self) -> bool:
        """Check if connected to device"""
        return self.bridge.is_connected()

    def get_device_status(self) -> DeviceStatus:
        """
        Get device status

        Returns:
            Device status information
        """
        return self.bridge.get_device_status()

    def get_device_did(self) -> str:
        """
        Get device DID

        Returns:
            Device DID string
        """
        if not self._device_did:
            self._device_did = self.bridge.get_device_did()
        return self._device_did

    def request_auth(self, challenge: Challenge, timeout_seconds: float = 30.0) -> HumanPresenceAssertion:
        """
        Request authentication and create assertion

        Args:
            challenge: Challenge object
            timeout_seconds: User response timeout

        Returns:
            Complete HumanPresenceAssertion

        Raises:
            ConnectionError: If not connected to device
            TimeoutError: If user doesn't respond in time
            ValueError: If authentication fails or device mismatch
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to device")

        if not self._device_did or not self._device_attestation:
            raise ValueError("Device not properly initialized")

        # Verify device DID matches challenge requirement
        if challenge.required_issuer_did != self._device_did:
            raise ValueError(
                f"Device DID mismatch: challenge requires {challenge.required_issuer_did}, "
                f"but connected device is {self._device_did}"
            )

        session_id = str(uuid.uuid4())

        try:
            # Create session log if storage available
            if self.store:
                action_params = {"action": challenge.action}
                self.store.create_session_log(session_id, self._device_did, challenge.action, action_params)

            # Build assertion skeleton
            assertion = self.builder.build_skeleton(
                challenge, self._device_did, self._device_attestation
            )

            # Compute h_doc for device
            h_doc = self.builder.compute_h_doc(assertion)

            # Check nonce freshness
            if self.store and not self.store.check_nonce(self._device_did, challenge.nonce):
                raise ValueError("Nonce has already been used (replay attack)")

            # Request authentication from device
            auth_result = self.bridge.request_authentication(
                h_doc=h_doc,
                nonce=challenge.nonce,
                display_title=challenge.display.title,
                display_risk=challenge.display.risk
            )

            # Inject authentication result
            assertion = self.builder.inject_auth_result(assertion, auth_result)

            # Mark nonce as used
            if self.store:
                self.store.mark_nonce_used(self._device_did, challenge.nonce, assertion.id)

            # Update session log
            if self.store:
                self.store.update_session_log(session_id, "completed", assertion.id)

            # Store audit record
            if self.store:
                action_params = {"action": challenge.action}
                self.store.store_audit_record(
                    assertion.id,
                    self._device_did,
                    challenge.action,
                    action_params,
                    auth_result.score,
                    False,  # chain_checked - local mode doesn't check chain
                    "local_mode",
                    auth_result.signature
                )

            logger.info(f"Authentication successful: assertion {assertion.id}")
            return assertion

        except Exception as e:
            # Update session log with error
            if self.store:
                self.store.update_session_log(session_id, "failed", error_message=str(e))
            raise

    def create_challenge_and_auth(self, action: str, action_params: Dict[str, Any], origin: str,
                                display_title: str, display_summary: str,
                                risk: str = "high") -> HumanPresenceAssertion:
        """
        Create challenge and request authentication in one call

        Args:
            action: Action type
            action_params: Action parameters
            origin: Request origin
            display_title: Display title for user
            display_summary: Display summary for user
            risk: Risk level

        Returns:
            Complete HumanPresenceAssertion
        """
        if not self._device_did:
            raise ValueError("Device not connected or initialized")

        # Build challenge
        challenge = self.builder.build_challenge(
            action, action_params, self._device_did, origin,
            display_title, display_summary, risk
        )

        # Request authentication
        return self.request_auth(challenge)

    def cancel_operation(self) -> bool:
        """
        Cancel current operation

        Returns:
            True if cancelled successfully
        """
        return self.bridge.cancel_operation()

    def initialize_device(self) -> bool:
        """
        Initialize device (first-time setup)

        Returns:
            True if initialization successful
        """
        return self.bridge.initialize_device()

    def wait_for_device_ready(self, timeout: float = 30.0) -> bool:
        """
        Wait for device ready event

        Args:
            timeout: Timeout in seconds

        Returns:
            True if device is ready
        """
        event = self.bridge.wait_for_ready_event(timeout)
        if event:
            # Update device info from ready event
            self._device_did = event.get("device_did")
            return True
        return False

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Run device diagnostics

        Returns:
            Diagnostic results
        """
        return self.bridge.run_diagnostics()

    def _on_device_event(self, device_port: str, connected: bool):
        """
        Handle device connect/disconnect events

        Args:
            device_port: Serial port of the device
            connected: True if device connected, False if disconnected
        """
        if connected:
            logger.info(f"Device plugged in: {device_port}")
        else:
            logger.info(f"Device unplugged: {device_port}")
            # Clear device info if our device was unplugged
            if device_port == self.bridge._connected_device:
                self._device_did = None
                self._device_attestation = None
                logger.warning("Active device was unplugged, clearing device information")

    def get_device_monitor_info(self) -> Dict[str, Any]:
        """
        Get device monitoring information

        Returns:
            Dict with monitoring details
        """
        return self.bridge.get_connection_info()

    def close(self):
        """Close client and cleanup resources"""
        self.bridge.stop_device_monitoring()
        self.disconnect()
        if self.store:
            self.store.close()