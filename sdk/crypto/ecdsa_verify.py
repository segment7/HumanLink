"""
ECDSA Signature Verification for HumanLink Protocol

Handles ECDSA P-256 signature verification using cryptography library
"""
import base64
from typing import Tuple
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature, encode_dss_signature
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature


class ECDSAVerifier:
    """ECDSA P-256 signature verifier"""

    @staticmethod
    def verify_signature(public_key_bytes: bytes, signed_hash: bytes, signature: bytes) -> bool:
        """
        Verify ECDSA P-256 signature

        Args:
            public_key_bytes: 64-byte uncompressed public key (x||y, no 0x04 prefix)
            signed_hash: 32-byte SHA-256 hash that was signed
            signature: 64-byte raw signature (r||s) or DER-encoded signature

        Returns:
            True if signature is valid

        Raises:
            ValueError: If input parameters are invalid
        """
        try:
            # Validate input lengths
            if len(public_key_bytes) != 64:
                raise ValueError("Public key must be 64 bytes (x||y)")
            if len(signed_hash) != 32:
                raise ValueError("Signed hash must be 32 bytes")

            # Reconstruct public key
            x = int.from_bytes(public_key_bytes[:32], 'big')
            y = int.from_bytes(public_key_bytes[32:], 'big')

            public_key = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()

            # Handle different signature formats
            if len(signature) == 64:
                # Raw format (r||s)
                r = int.from_bytes(signature[:32], 'big')
                s = int.from_bytes(signature[32:], 'big')
                der_signature = encode_dss_signature(r, s)
            else:
                # Assume DER format
                der_signature = signature

            # Verify signature using prehashed data
            public_key.verify(der_signature, signed_hash, ec.ECDSA(hashes.Prehashed()))
            return True

        except InvalidSignature:
            return False
        except Exception as e:
            raise ValueError(f"Signature verification error: {e}")

    @staticmethod
    def verify_signature_from_base64(public_key_b64: str, signed_hash_hex: str, signature_b64: str) -> bool:
        """
        Verify signature from base64/hex encoded inputs

        Args:
            public_key_b64: Base64 encoded public key
            signed_hash_hex: Hex encoded signed hash
            signature_b64: Base64 encoded signature

        Returns:
            True if signature is valid
        """
        try:
            public_key_bytes = base64.b64decode(public_key_b64)
            signed_hash = bytes.fromhex(signed_hash_hex)
            signature = base64.b64decode(signature_b64)

            return ECDSAVerifier.verify_signature(public_key_bytes, signed_hash, signature)

        except Exception as e:
            raise ValueError(f"Failed to decode inputs: {e}")

    @staticmethod
    def extract_public_key_from_did(did_key: str) -> bytes:
        """
        Extract public key bytes from did:key

        Args:
            did_key: DID key in format did:key:z...

        Returns:
            64-byte public key (x||y)

        Raises:
            ValueError: If DID format is invalid
        """
        if not did_key.startswith("did:key:z"):
            raise ValueError("Invalid DID key format")

        # Extract base32 part
        base32_part = did_key[9:]  # Remove "did:key:z"

        # Base32 decode (Crockford alphabet)
        try:
            decoded = ECDSAVerifier._base32_decode(base32_part)
        except Exception as e:
            raise ValueError(f"Failed to decode DID: {e}")

        # Remove multicodec prefix (0x12 0x20 for secp256r1)
        if len(decoded) < 66 or decoded[0] != 0x12 or decoded[1] != 0x20:
            raise ValueError("Invalid multicodec prefix in DID")

        return decoded[2:]  # Return 64-byte public key

    @staticmethod
    def _base32_decode(encoded: str) -> bytes:
        """
        Decode Crockford Base32

        Args:
            encoded: Base32 encoded string

        Returns:
            Decoded bytes
        """
        # Crockford Base32 alphabet
        alphabet = "abcdefghijklmnopqrstuvwxyz234567"

        # Create lookup table
        lookup = {char: i for i, char in enumerate(alphabet)}

        # Decode
        result = bytearray()
        buffer = 0
        bits = 0

        for char in encoded.lower():
            if char not in lookup:
                raise ValueError(f"Invalid Base32 character: {char}")

            buffer = (buffer << 5) | lookup[char]
            bits += 5

            if bits >= 8:
                result.append((buffer >> (bits - 8)) & 0xFF)
                bits -= 8

        return bytes(result)

    @staticmethod
    def verify_assertion_signature(assertion: dict, device_did: str) -> bool:
        """
        Verify HumanPresenceAssertion signature

        Args:
            assertion: HumanPresenceAssertion dictionary
            device_did: Expected device DID

        Returns:
            True if signature is valid
        """
        try:
            # Extract proof section
            proof = assertion.get("proof")
            if not proof:
                raise ValueError("Missing proof section")

            # Verify verification method matches device DID
            verification_method = proof.get("verificationMethod", "")
            expected_method = f"{device_did}#key-0"
            if verification_method != expected_method:
                raise ValueError(f"Verification method mismatch: {verification_method} != {expected_method}")

            # Extract signature components
            signed_hash_hex = proof.get("signedHash")
            signature_b64 = proof.get("signature")

            if not signed_hash_hex or not signature_b64:
                raise ValueError("Missing signedHash or signature in proof")

            # Extract public key from DID
            public_key_bytes = ECDSAVerifier.extract_public_key_from_did(device_did)

            # Convert inputs
            signed_hash = bytes.fromhex(signed_hash_hex)
            signature = base64.b64decode(signature_b64)

            # Verify signature
            return ECDSAVerifier.verify_signature(public_key_bytes, signed_hash, signature)

        except Exception as e:
            raise ValueError(f"Signature verification failed: {e}")