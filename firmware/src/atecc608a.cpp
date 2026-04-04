/**
 * ATECC608A Secure Element Implementation
 *
 * Wraps ArduinoECCX08 to provide sign() and getPublicKey().
 *
 * Mock path: generates a deterministic fake ECDSA signature (0xAA...55 pattern)
 * and a fixed public key so the downstream JSON assembly can be exercised.
 *
 * Real path: uses slot 0. On first boot (config zone unlocked) it calls
 * ECCX08.begin() which initialises the chip; key generation happens lazily
 * when sign() is called for the first time on a blank slot via generatePrivateKey().
 */

#include "atecc608a.h"

#ifndef HUMANLINK_MOCK_HARDWARE
#include <ArduinoECCX08.h>

static const int KEY_SLOT = 0;
#endif

// ── Mock constants ─────────────────────────────────────────────────────────
#ifdef HUMANLINK_MOCK_HARDWARE
// Fixed 64-byte "public key" for test DID derivation
static const uint8_t MOCK_PUBKEY[64] = {
    // X coordinate (32 bytes)
    0x6B,0x17,0xD1,0xF2, 0xE1,0x2C,0x42,0x47,
    0xF8,0xBC,0xE6,0xE5, 0x63,0xA4,0x40,0xF2,
    0x77,0x03,0x7D,0x81, 0x2D,0xEB,0x33,0xA0,
    0xF4,0xA1,0x39,0x45, 0xD8,0x98,0xC2,0x96,
    // Y coordinate (32 bytes)
    0x4F,0xE3,0x42,0xE2, 0xFE,0x1A,0x7F,0x9B,
    0x8E,0xE7,0xEB,0x4A, 0x7C,0x0F,0x9E,0x16,
    0x2B,0xCE,0x33,0x57, 0x6B,0x31,0x5E,0xCE,
    0xCB,0xB6,0x40,0x68, 0x37,0xBF,0x51,0xF5
};
#endif

// ── begin ──────────────────────────────────────────────────────────────────
bool SecureEnclave::begin() {
#ifdef HUMANLINK_MOCK_HARDWARE
    _provisioned = true;
    Serial.println("[SE] MOCK: ATECC608A ready (slot 0 provisioned)");
    return true;
#else
    if (!ECCX08.begin()) {
        Serial.println("[SE] ERROR: ATECC608A not found on I2C");
        return false;
    }

    // Check lock status
    if (!ECCX08.locked()) {
        Serial.println("[SE] Chip unlocked — provisioning key slot 0...");
        // Generate a new private key in slot 0 and lock the config zone
        uint8_t pub_discard[64];
        if (!ECCX08.generatePrivateKey(KEY_SLOT, pub_discard)) {
            Serial.println("[SE] ERROR: key generation failed");
            return false;
        }
        // Lock the configuration zone to protect the key
        if (!ECCX08.lock()) {
            Serial.println("[SE] WARNING: failed to lock config zone");
            // Continue anyway; key is still usable
        }
    }

    _provisioned = true;
    Serial.println("[SE] ATECC608A ready");
    return true;
#endif
}

// ── sign ──────────────────────────────────────────────────────────────────
int SecureEnclave::sign(const uint8_t digest[32], uint8_t sig_out[HL_SIG_LEN]) {
#ifdef HUMANLINK_MOCK_HARDWARE
    // Deterministic mock signature: first 32 bytes = digest XOR 0xAA,
    // second 32 bytes = digest XOR 0x55 (r and s components)
    for (int i = 0; i < 32; i++) {
        sig_out[i]      = digest[i] ^ 0xAA;
        sig_out[i + 32] = digest[i] ^ 0x55;
    }
    Serial.println("[SE] MOCK: signed digest with mock ECDSA-P256");
    return HL_OK;
#else
    if (!_provisioned) return HL_ERR_SE;

    // Load the digest into TempKey via Nonce command (required before Sign)
    if (!ECCX08.nonce(digest)) {
        return HL_ERR_SE;
    }
    if (!ECCX08.ecSign(KEY_SLOT, digest, sig_out)) {
        return HL_ERR_SIGN_FAIL;
    }
    return HL_OK;
#endif
}

// ── getPublicKey ──────────────────────────────────────────────────────────
int SecureEnclave::getPublicKey(uint8_t pubkey_out[HL_PUBKEY_LEN]) {
#ifdef HUMANLINK_MOCK_HARDWARE
    memcpy(pubkey_out, MOCK_PUBKEY, HL_PUBKEY_LEN);
    return HL_OK;
#else
    if (!_provisioned) return HL_ERR_SE;

    if (!ECCX08.generatePublicKey(KEY_SLOT, pubkey_out)) {
        return HL_ERR_SE;
    }
    return HL_OK;
#endif
}

// ── isProvisioned ─────────────────────────────────────────────────────────
bool SecureEnclave::isProvisioned() {
    return _provisioned;
}
