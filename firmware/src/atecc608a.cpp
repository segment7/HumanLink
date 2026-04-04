/**
 * ATECC608A Secure Element Implementation
 *
 * Wraps ArduinoECCX08 to provide sign() and getPublicKey().
 *
 * Real path: uses slot 0. On first boot (config zone unlocked) it calls
 * ECCX08.begin() which initialises the chip; key generation happens lazily
 * when sign() is called for the first time on a blank slot via generatePrivateKey().
 */

#include "atecc608a.h"

#include <ArduinoECCX08.h>
#include "utility/ECCX08DefaultTLSConfig.h"

static const int KEY_SLOT = 0;

// ── begin ──────────────────────────────────────────────────────────────────
bool SecureEnclave::begin() {
    if (!ECCX08.begin()) {
        Serial.println("[SE] ERROR: ATECC608A not found on I2C");

        // I2C device scan for diagnosis
        Serial.println("[SE] Scanning I2C bus...");
        int deviceCount = 0;
        for (int addr = 1; addr < 127; addr++) {
            Wire.beginTransmission(addr);
            if (Wire.endTransmission() == 0) {
                Serial.printf("[SE] I2C device found at address 0x%02X\n", addr);
                deviceCount++;
            }
        }
        if (deviceCount == 0) {
            Serial.println("[SE] No I2C devices found - check wiring");
        } else {
            Serial.printf("[SE] Found %d I2C device(s), but ATECC608A not responding\n", deviceCount);
            Serial.println("[SE] ATECC608A should be at address 0x60");
        }
        return false;
    }

    // Check lock status and configuration
    bool is_locked = ECCX08.locked();
    Serial.printf("[SE] Chip lock status: %s\n", is_locked ? "LOCKED" : "UNLOCKED");

    if (!is_locked) {
        Serial.println("[SE] Chip unlocked — provisioning key slot 0...");

        // First, write the default configuration if needed
        //Serial.println("[SE] Writing default configuration...");
        //if (!ECCX08.writeConfiguration()) {
        //    Serial.println("[SE] ERROR: Failed to write configuration");
        //    return false;
        //}
        //Serial.println("[SE] Configuration written successfully");

        // Lock the configuration zone first
        if (!ECCX08.lock()) {
            Serial.println("[SE] ERROR: Failed to lock config zone");
            return false;
        }
        Serial.println("[SE] Config zone locked successfully");

        // Now generate a new private key in slot 0
        Serial.println("[SE] Generating new key for slot 0...");
        uint8_t pub_discard[64];
        if (!ECCX08.generatePrivateKey(KEY_SLOT, pub_discard)) {
            Serial.println("[SE] ERROR: key generation failed");
            Serial.println("[SE] This may indicate:");
            Serial.println("[SE]   - Chip configuration incompatible");
            Serial.println("[SE]   - Power supply issues (need stable 3.3V)");
            Serial.println("[SE]   - Try different ATECC608A chip");
            return false;
        }
        Serial.println("[SE] New key generated successfully");
    } else {
        Serial.println("[SE] Chip is already locked, checking existing key...");

        // Try to verify we can use the existing key
        uint8_t test_key[64];
        if (!ECCX08.generatePublicKey(KEY_SLOT, test_key)) {
            Serial.println("[SE] WARNING: Cannot access key in slot 0");
            Serial.println("[SE] Slot may be locked or configured to prohibit key operations");
            Serial.println("[SE] Continuing anyway - will attempt to export public key when needed");

            // Mark as provisioned but note that key operations may be limited
            _provisioned = true;
            Serial.println("[SE] ATECC608A ready (limited key operations)");
            return true;
        }
        Serial.println("[SE] Existing key in slot 0 is accessible");
    }

    _provisioned = true;
    Serial.println("[SE] ATECC608A ready");
    return true;
}

// ── sign ──────────────────────────────────────────────────────────────────
int SecureEnclave::sign(const uint8_t digest[32], uint8_t sig_out[HL_SIG_LEN]) {
    if (!_provisioned) return HL_ERR_SE;

    // Load the digest into TempKey via Nonce command (required before Sign)
    if (!ECCX08.nonce(digest)) {
        return HL_ERR_SE;
    }
    if (!ECCX08.ecSign(KEY_SLOT, digest, sig_out)) {
        return HL_ERR_SIGN_FAIL;
    }
    return HL_OK;
}

// ── getPublicKey ──────────────────────────────────────────────────────────
int SecureEnclave::getPublicKey(uint8_t pubkey_out[HL_PUBKEY_LEN]) {
    if (!_provisioned) return HL_ERR_SE;

    // Try to get public key from slot 0
    if (!ECCX08.generatePublicKey(KEY_SLOT, pubkey_out)) {
        Serial.println("[SE] WARNING: Failed to generate public key from slot 0");
        Serial.println("[SE] This may indicate slot is locked or configured to prohibit key operations");

        // Try alternative approaches to get public key
        // Note: Some ATECC608A configurations may not allow public key generation
        // from certain slots, but we should still try to continue
        return HL_ERR_SE;
    }
    return HL_OK;
}

// ── isProvisioned ─────────────────────────────────────────────────────────
bool SecureEnclave::isProvisioned() {
    return _provisioned;
}

// ── isLocked ──────────────────────────────────────────────────────────────
bool SecureEnclave::isLocked() {
    if (!_provisioned) return false;
    return ECCX08.locked();
}
