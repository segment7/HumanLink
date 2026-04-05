"""
USB Serial Bridge for HumanLink Device Communication

Handles USB Serial communication with HumanLink ESP32 devices
"""
import json
import time
import logging
from typing import Dict, Any, Optional, List, Callable
import serial
import serial.tools.list_ports
from threading import RLock, Thread, Event
import weakref

from data_types import AuthResult, DeviceStatus, DeviceState, ErrorCode


logger = logging.getLogger(__name__)


class USBBridge:
    """USB Serial communication bridge for HumanLink devices"""

    def __init__(self, port: Optional[str] = None, baud_rate: int = 115200, timeout: float = 30.0):
        """
        Initialize USB bridge

        Args:
            port: Serial port (auto-detect if None)
            baud_rate: Serial baud rate
            timeout: Communication timeout in seconds
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None
        self.lock = RLock()
        self._device_did: Optional[str] = None

        # Device monitoring
        self._monitoring = False
        self._monitor_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._device_callbacks: List[Callable[[str, bool], None]] = []
        self._last_known_devices: set = set()
        self._connected_device: Optional[str] = None

    def find_humanlink_devices(self) -> List[str]:
        """
        Find connected HumanLink devices

        Returns:
            List of serial port names
        """
        ports = []
        for port_info in serial.tools.list_ports.comports():
            # Look for ESP32 devices (CH340, CP210x, etc.)
            if any(chip in port_info.description.lower() for chip in ['ch340', 'cp210', 'usb', 'serial']):
                ports.append(port_info.device)
        return ports

    def connect(self) -> bool:
        """
        Connect to HumanLink device

        Returns:
            True if connected successfully
        """
        with self.lock:
            if self.connection and self.connection.is_open:
                return True

            try:
                # Auto-detect port if not specified
                if not self.port:
                    ports = self.find_humanlink_devices()
                    if not ports:
                        logger.error("No HumanLink devices found")
                        return False
                    self.port = ports[0]  # Use first found device

                logger.info(f"Connecting to HumanLink device on {self.port}")
                self.connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baud_rate,
                    timeout=2.0,  # Shorter timeout for connection
                    write_timeout=2.0
                )

                self.connection.setDTR(False)
                self.connection.setRTS(False)

                time.sleep(1.5) 
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()

                # Clear any pending data
                time.sleep(0.1)
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()

                # Clear any startup messages first
                time.sleep(0.5)  # Give device time to settle
                self.connection.reset_input_buffer()

                # Test device status directly instead of waiting for ready event
                try:
                    if self._test_device_status():
                        logger.info("HumanLink device connected and responding")
                        self._connected_device = self.port
                        return True
                    else:
                        logger.warning("Device not responding or not a HumanLink device")
                        self.disconnect()
                        return False
                except Exception as e:
                    logger.error(f"Device status test failed: {e}")
                    self.disconnect()
                    return False

            except serial.SerialException as e:
                logger.error(f"Failed to connect: {e}")
                return False

    def disconnect(self):
        """Disconnect from device"""
        with self.lock:
            if self.connection and self.connection.is_open:
                try:
                    self.connection.close()
                except:
                    pass
            self.connection = None
            self._device_did = None
            self._connected_device = None

    def is_connected(self) -> bool:
        """Check if connected to device"""
        with self.lock:
            return self.connection and self.connection.is_open

    def _test_device_status(self) -> bool:
        """
        Test if device is a HumanLink device by checking status

        Returns:
            True if device responds with valid HumanLink status
        """
        try:
            logger.info("Testing device status...")
            response = self._send_command({"cmd": "status"},timeout=3.0)

            # Check if response has expected HumanLink fields
            if (response.get("status") == "ok" and
                "state" in response and
                "protocol" in response and
                "device_did" in response):
                logger.info(f"HumanLink device detected: {response.get('device_did', 'unknown')}")
                logger.info(f"Device state: {response.get('state')}, Protocol: {response.get('protocol')}")
                return True
            else:
                logger.warning(f"Invalid HumanLink response: {response}")
                return False
        except Exception as e:
            logger.error(f"Device status test failed: {e}")
            return False

    def _ping_device(self) -> bool:
        """
        Simple ping to check basic connectivity

        Returns:
            True if device responds
        """
        try:
            response = self._send_command({"cmd": "status"},timeout=3.0)
            return response.get("status") == "ok"
        except Exception as e:
            logger.error(f"Device ping failed: {e}")
            return False

    def _send_command(self, command: Dict[str, Any], timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Send JSON command to device and wait for response

        Args:
            command: Command dictionary
            timeout: Response timeout (uses default if None)

        Returns:
            Response dictionary

        Raises:
            ConnectionError: If not connected
            TimeoutError: If no response received
            ValueError: If invalid response
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to device")

        if timeout is None:
            timeout = self.timeout

        # Send command
        cmd_json = json.dumps(command) + '\n'
        try:
            self.connection.write(cmd_json.encode('utf-8'))
            self.connection.flush()
        except serial.SerialException as e:
            raise ConnectionError(f"Failed to send command: {e}")

        # Read response - try multiple lines as ESP32 may send debug info first
        start_time = time.time()
        response_line = ""

        while time.time() - start_time < timeout:
            try:
                if self.connection.in_waiting > 0:
                    line = self.connection.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        # Try to parse as JSON - if successful, this is our response
                        try:
                            response = json.loads(line)
                            return response
                        except json.JSONDecodeError:
                            # Not JSON, might be debug output, continue reading
                            logger.debug(f"Non-JSON line from device: {line}")
                            continue
                else:
                    time.sleep(0.01)  # Small delay to prevent busy waiting
            except serial.SerialException as e:
                raise ConnectionError(f"Failed to read response: {e}")
            except UnicodeDecodeError:
                # Skip invalid characters
                continue
        else:
            raise TimeoutError(f"No valid JSON response received within {timeout} seconds")

    def get_device_status(self) -> DeviceStatus:
        """
        Get device status

        Returns:
            Device status information
        """
        response = self._send_command({"cmd": "status"}, timeout=3.0)

        if response.get("status") != "ok":
            raise ValueError(f"Device error: {response.get('msg', 'Unknown error')}")

        return DeviceStatus(
            status=response["status"],
            state=DeviceState(response["state"]),
            provisioned=response["provisioned"],
            enrolled=response["enrolled"],
            protocol=response["protocol"],
            device_did=response["device_did"],
            needs_init=response["needs_init"]
        )

    def get_device_did(self) -> str:
        """
        Get device DID

        Returns:
            Device DID string
        """
        if self._device_did:
            return self._device_did

        response = self._send_command({"cmd": "getDID"},timeout=3.0)

        if response.get("status") != "ok":
            raise ValueError(f"Failed to get DID: {response.get('msg', 'Unknown error')}")

        self._device_did = response["device_did"]
        return self._device_did

    def request_authentication(self, h_doc: str, nonce: str, display_title: str,
                             display_risk: str = "high") -> AuthResult:
        """
        Request authentication from device

        Args:
            h_doc: Document hash (64 hex chars)
            nonce: Nonce (16 hex chars)
            display_title: Title to show user
            display_risk: Risk level

        Returns:
            Authentication result

        Raises:
            TimeoutError: If user doesn't respond in time
            ValueError: If authentication fails
        """
        command = {
            "cmd": "auth",
            "h_doc": h_doc,
            "nonce": nonce,
            "display": {
                "title": display_title,
                "risk": display_risk
            }
        }

        # Use longer timeout for user interaction
        response = self._send_command(command, timeout=self.timeout)

        if response.get("status") == "err":
            error_code = response.get("code", 0)
            error_msg = response.get("msg", "Unknown error")

            if error_code == ErrorCode.ERR_TIMEOUT:
                raise TimeoutError("User did not respond in time")
            elif error_code == ErrorCode.ERR_NO_MATCH:
                raise ValueError("Fingerprint not recognized")
            elif error_code == ErrorCode.ERR_NOT_ENROLLED:
                raise ValueError("No fingerprints enrolled")
            else:
                raise ValueError(f"Authentication failed: {error_msg}")

        # Parse successful response
        return AuthResult(
            matched_id=response["matched_id"],
            score=response["score"],
            sensor_serial=response["sensor_serial"],
            signature=response["sig"],
            public_key=response["pubkey"],
            signed_hash=response["signed_hash"],
            nonce=response["nonce"]
        )

    def cancel_operation(self) -> bool:
        """
        Cancel current operation

        Returns:
            True if cancelled successfully
        """
        try:
            response = self._send_command({"cmd": "cancel"}, timeout=10.0)
            return response.get("status") == "ok"
        except Exception as e:
            logger.warning(f"Cancel operation failed: {e}")
            return False

    def initialize_device(self) -> bool:
        """
        Initialize device (enroll fingerprints, provision secure element)

        Returns:
            True if initialization successful
        """
        try:
            # This may take a long time as it includes fingerprint enrollment
            response = self._send_command({"cmd": "init"}, timeout=300.0)
            return response.get("status") == "ok"
        except Exception as e:
            logger.error(f"Device initialization failed: {e}")
            return False

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        Run hardware diagnostics

        Returns:
            Diagnostic results
        """
        response = self._send_command({"cmd": "diag"}, timeout=20.0)
        return response

    def wait_for_ready_event(self, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """
        Wait for device ready event

        Args:
            timeout: Timeout in seconds

        Returns:
            Ready event data or None if timeout
        """
        if not self.is_connected():
            return None

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                if self.connection.in_waiting > 0:
                    line = self.connection.readline().decode('utf-8').strip()
                    if line:
                        try:
                            event = json.loads(line)
                            if event.get("event") == "ready":
                                return event
                        except json.JSONDecodeError:
                            continue
                else:
                    time.sleep(0.1)
            except serial.SerialException:
                break

        return None

    def start_device_monitoring(self, poll_interval: float = 2.0):
        """
        Start background device monitoring for plug/unplug events

        Args:
            poll_interval: Time between device scans in seconds
        """
        if self._monitoring:
            return

        logger.info("Starting device monitoring...")
        self._monitoring = True
        self._stop_event.clear()
        self._monitor_thread = Thread(target=self._device_monitor_loop, args=(poll_interval,))
        self._monitor_thread.daemon = True
        self._monitor_thread.start()

    def stop_device_monitoring(self):
        """Stop device monitoring"""
        if not self._monitoring:
            return

        logger.info("Stopping device monitoring...")
        self._monitoring = False
        self._stop_event.set()

        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None

    def add_device_callback(self, callback: Callable[[str, bool], None]):
        """
        Add callback for device connect/disconnect events

        Args:
            callback: Function called with (device_port, is_connected)
        """
        self._device_callbacks.append(callback)

    def remove_device_callback(self, callback: Callable[[str, bool], None]):
        """Remove device event callback"""
        if callback in self._device_callbacks:
            self._device_callbacks.remove(callback)

    def _device_monitor_loop(self, poll_interval: float):
        """Background loop for monitoring device connections"""
        logger.info(f"Device monitoring started (polling every {poll_interval}s)")

        while not self._stop_event.wait(poll_interval):
            try:
                current_devices = set(self.find_humanlink_devices())

                # Check for newly connected devices
                new_devices = current_devices - self._last_known_devices
                for device in new_devices:
                    logger.info(f"Device connected: {device}")
                    self._notify_device_event(device, True)

                    # Try to auto-connect if no device currently connected
                    if not self.is_connected():
                        logger.info(f"Attempting auto-connection to {device}")
                        self.port = device
                        if self.connect():
                            logger.info(f"Auto-connected to {device}")
                            self._connected_device = device
                        else:
                            logger.warning(f"Auto-connection to {device} failed")

                # Check for disconnected devices
                removed_devices = self._last_known_devices - current_devices
                for device in removed_devices:
                    logger.info(f"Device disconnected: {device}")
                    self._notify_device_event(device, False)

                    # If our connected device was removed, disconnect
                    if device == self._connected_device:
                        logger.warning(f"Connected device {device} was unplugged")
                        self.disconnect()
                        self._connected_device = None

                # Check if current connection is still valid
                if self.is_connected() and self._connected_device:
                    if self._connected_device not in current_devices:
                        logger.warning(f"Current connection {self._connected_device} no longer available")
                        self.disconnect()
                        self._connected_device = None

                self._last_known_devices = current_devices

            except Exception as e:
                logger.error(f"Error in device monitoring loop: {e}")

        logger.info("Device monitoring stopped")

    def _notify_device_event(self, device: str, connected: bool):
        """Notify all callbacks about device events"""
        for callback in self._device_callbacks[:]:  # Copy to avoid modification during iteration
            try:
                callback(device, connected)
            except Exception as e:
                logger.error(f"Error in device callback: {e}")

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get detailed connection information

        Returns:
            Dict with connection details
        """
        return {
            "connected": self.is_connected(),
            "port": self.port,
            "connected_device": self._connected_device,
            "available_devices": self.find_humanlink_devices(),
            "monitoring": self._monitoring,
            "device_did": self._device_did
        }

    def __del__(self):
        """Cleanup on destruction"""
        self.stop_device_monitoring()
        self.disconnect()