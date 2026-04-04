/**
 * ATECC608A Secure Element Wrapper
 *
 * Wraps ArduinoECCX08 library to provide:
 *   - One-time provisioning (key slot 0 = device key)
 *   - ECDSA P-256 signing of arbitrary 32-byte digest
 *   - Public key export (for DID:key derivation on PC SDK side)
 *
 * I2C wiring: GPIO21 (SDA), GPIO22 (SCL)
 *
 * Key slot assignment (ATECC608A has 16 slots):
 *   Slot 0 : Device private key (ECDSA P-256, locked, never extractable)
 *   Slot 8 : Device attestation certificate (optional future use)
 */

#pragma once

#include <Arduino.h>
#include "protocol.h"

class SecureEnclave {
public:
    SecureEnclave() = default;

    /**
     * Initialize I2C and verify ATECC608A is present.
     * On first boot (unlocked), provisions a new key pair in slot 0.
     * @return true on success
     */
    bool begin();

    /**
     * Sign a 32-byte digest using the device private key (slot 0).
     * Private key never leaves the chip.
     *
     * @param digest   32-byte SHA-256 hash to sign
     * @param sig_out  64-byte output buffer (r‖s, raw P-256)
     * @return HL_OK or HL_ERR_SE / HL_ERR_SIGN_FAIL
     */
    int sign(const uint8_t digest[32], uint8_t sig_out[HL_SIG_LEN]);

    /**
     * Export the 64-byte uncompressed public key (without 0x04 prefix).
     * Used by PC SDK to derive did:key.
     *
     * @param pubkey_out  64-byte output buffer
     * @return HL_OK or HL_ERR_SE
     */
    int getPublicKey(uint8_t pubkey_out[HL_PUBKEY_LEN]);

    /**
     * Returns true if the device key has been provisioned and locked.
     */
    bool isProvisioned();

private:
    bool _provisioned = false;
};
