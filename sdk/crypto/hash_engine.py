"""
Hash Engine for HumanLink Protocol

Implements action hash and document hash computation according to protocol specs
"""
import json
import hashlib
import struct
from typing import Dict, Any, List, Tuple


class HashEngine:
    """Hash computation engine for HumanLink protocol"""

    FIELD_SEPARATOR = b'\x1f'  # ASCII Unit Separator

    @staticmethod
    def compute_action_hash(action: str, params: Dict[str, Any], nonce: str, required_issuer_did: str) -> str:
        """
        Compute actionHash according to protocol specification

        Args:
            action: Action type (e.g., "transfer")
            params: Action parameters
            nonce: 16-character hex nonce
            required_issuer_did: Required issuer DID

        Returns:
            SHA-256 hash in hex format
        """
        # Sort params by key (lexicographic order)
        sorted_params = sorted(params.items())

        # Build components list
        components = [action.encode('utf-8')]

        # Add sorted parameters as key=value
        for key, value in sorted_params:
            param_str = f"{key}={value}"
            components.append(param_str.encode('utf-8'))

        # Add nonce and DID
        components.extend([
            nonce.encode('utf-8'),
            required_issuer_did.encode('utf-8')
        ])

        # Join with field separator
        raw_data = HashEngine.FIELD_SEPARATOR.join(components)

        # Compute SHA-256
        return hashlib.sha256(raw_data).hexdigest()

    @staticmethod
    def compute_h_doc(assertion_skeleton: Dict[str, Any]) -> bytes:
        """
        Compute h_doc hash from assertion skeleton (without proof field)

        Args:
            assertion_skeleton: Assertion dict without proof field

        Returns:
            32-byte SHA-256 hash
        """
        # Canonicalize JSON (sorted keys, compact format, UTF-8)
        canonical_json = json.dumps(
            assertion_skeleton,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False
        )

        # Encode to UTF-8 and hash
        return hashlib.sha256(canonical_json.encode('utf-8')).digest()

    @staticmethod
    def compute_h_doc_hex(assertion_skeleton: Dict[str, Any]) -> str:
        """
        Compute h_doc hash and return as hex string

        Args:
            assertion_skeleton: Assertion dict without proof field

        Returns:
            64-character hex string
        """
        return HashEngine.compute_h_doc(assertion_skeleton).hex()

    @staticmethod
    def rebuild_signed_hash(matched_id: int, score: int, sensor_serial: bytes,
                          nonce: bytes, h_doc: bytes) -> bytes:
        """
        Rebuild signedHash for verification

        Args:
            matched_id: Matched template ID
            score: Match confidence score
            sensor_serial: 32-byte sensor serial number
            nonce: 8-byte nonce
            h_doc: 32-byte document hash

        Returns:
            32-byte signed hash
        """
        if len(sensor_serial) != 32:
            raise ValueError("sensor_serial must be 32 bytes")
        if len(nonce) != 8:
            raise ValueError("nonce must be 8 bytes")
        if len(h_doc) != 32:
            raise ValueError("h_doc must be 32 bytes")

        # Build payload: matched_id(2) + score(2) + sensor_serial(32) + nonce(8) + h_doc(32)
        payload = (
            struct.pack('>HH', matched_id, score) +  # Big-endian uint16s
            sensor_serial +
            nonce +
            h_doc
        )

        if len(payload) != 76:
            raise ValueError(f"Payload length should be 76 bytes, got {len(payload)}")

        return hashlib.sha256(payload).digest()

    @staticmethod
    def rebuild_signed_hash_hex(matched_id: int, score: int, sensor_serial_hex: str,
                               nonce_hex: str, h_doc_hex: str) -> str:
        """
        Rebuild signedHash from hex strings

        Args:
            matched_id: Matched template ID
            score: Match confidence score
            sensor_serial_hex: 64-char hex string (32 bytes)
            nonce_hex: 16-char hex string (8 bytes)
            h_doc_hex: 64-char hex string (32 bytes)

        Returns:
            64-character hex hash
        """
        try:
            sensor_serial = bytes.fromhex(sensor_serial_hex)
            nonce = bytes.fromhex(nonce_hex)
            h_doc = bytes.fromhex(h_doc_hex)
        except ValueError as e:
            raise ValueError(f"Invalid hex input: {e}")

        return HashEngine.rebuild_signed_hash(matched_id, score, sensor_serial, nonce, h_doc).hex()

    @staticmethod
    def validate_hash_inputs(action: str, params: Dict[str, Any], nonce: str, did: str) -> List[str]:
        """
        Validate inputs for hash computation

        Args:
            action: Action string
            params: Parameters dict
            nonce: Nonce string
            did: DID string

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not action or not isinstance(action, str):
            errors.append("action must be a non-empty string")

        if not isinstance(params, dict):
            errors.append("params must be a dictionary")

        if not nonce or not isinstance(nonce, str) or len(nonce) != 16:
            errors.append("nonce must be a 16-character hex string")
        else:
            try:
                int(nonce, 16)
            except ValueError:
                errors.append("nonce must be valid hex")

        if not did or not isinstance(did, str) or not did.startswith("did:key:"):
            errors.append("required_issuer_did must be a valid DID")

        return errors

    @staticmethod
    def hex_to_bytes(hex_str: str, expected_length: int) -> bytes:
        """
        Convert hex string to bytes with length validation

        Args:
            hex_str: Hex string
            expected_length: Expected byte length

        Returns:
            Byte array

        Raises:
            ValueError: If invalid hex or wrong length
        """
        if not hex_str:
            raise ValueError("hex string cannot be empty")

        if len(hex_str) != expected_length * 2:
            raise ValueError(f"hex string must be {expected_length * 2} characters for {expected_length} bytes")

        try:
            return bytes.fromhex(hex_str)
        except ValueError:
            raise ValueError("invalid hex string")

    @staticmethod
    def bytes_to_hex(data: bytes) -> str:
        """
        Convert bytes to hex string

        Args:
            data: Byte data

        Returns:
            Lowercase hex string
        """
        return data.hex().lower()