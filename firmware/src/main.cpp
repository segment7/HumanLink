/**
 * HumanLink Firmware — Safe Enclave Main
 *
 * State machine:
 *   IDLE → (JSON cmd received on USB Serial) → AUTHORIZING
 *   AUTHORIZING:
 *     1. Parse H_doc + display info from JSON
 *     2. Show action summary on Serial (future: OLED)
 *     3. Fetch sensor SN (used in signed payload)
 *     4. Run JM-101 AutoIdentify (blocks until finger or timeout)
 *     5. Build signedHash = SHA-256(matched_id ‖ score ‖ sensor_sn ‖ h_doc)
 *     6. ATECC608A.sign(signedHash) → ECDSA-P256 signature
 *     7. Send JSON response to PC SDK
 *   IDLE
 *
 * USB Serial framing: newline-delimited JSON (max 512 bytes per message)
 *
 * Input example:
 *   {"cmd":"auth","h_doc":"aabbcc...","nonce":"deadbeef01234567",
 *    "display":{"title":"Transfer $50 to Alice","risk":"high"}}
 *
 * Output on success:
 *   {"status":"ok","matched_id":1,"score":188,
 *    "sensor_serial":"deadbeef...","sig":"base64...",
 *    "pubkey":"base64..."}
 *
 * Output on error:
 *   {"status":"err","code":2,"msg":"no match"}
 *
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include "protocol.h"
#include "jm101.h"
#include "atecc608a.h"

// ── Hardware pins ──────────────────────────────────────────────────────────
// JM-101 UART: RX=GPIO16, TX=GPIO17 (Serial2 on ESP32)
// ATECC608A  : SDA=GPIO21, SCL=GPIO22 (Wire default on ESP32)
static const int JM101_RX_PIN = 16;
static const int JM101_TX_PIN = 17;

// ── Fingerprint timeout ────────────────────────────────────────────────────
static const uint32_t AUTH_TIMEOUT_MS = 20000;  // 20 s

// ── Protocol version ───────────────────────────────────────────────────────
static const char* PROTOCOL_VERSION = "0.3";

// ── Auto-initialization settings ──────────────────────────────────────────
static const int MIN_REQUIRED_FINGERPRINTS = 1;  // At least 1 fingerprint needed
static const int MAX_ENROLLMENT_ATTEMPTS = 3;    // Max retries per enrollment

// ── Module instances ───────────────────────────────────────────────────────
static JM101         sensor(Serial2);
static SecureEnclave se;

// ── Device state ────────────────────────────────────────────────────────────
static char device_did[HL_DID_MAX_LEN] = {0};  // Cached did:key for responses

// ── State ──────────────────────────────────────────────────────────────────
enum class State {
    INITIALIZING,    // First boot: need to enroll fingerprints
    IDLE,           // Ready for auth commands
    AUTHORIZING,    // Processing auth request
    ENROLLING       // Fingerprint enrollment in progress
};
static State state = State::INITIALIZING;

// ── Internal helpers ───────────────────────────────────────────────────────

// Hex-decode a lowercase hex string into bytes. Returns true on success.
static bool hexDecode(const char* hex, uint8_t* out, size_t expected_len) {
    size_t slen = strlen(hex);
    if (slen != expected_len * 2) return false;
    for (size_t i = 0; i < expected_len; i++) {
        char hi = hex[i * 2];
        char lo = hex[i * 2 + 1];
        auto nibble = [](char c) -> int8_t {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return c - 'a' + 10;
            if (c >= 'A' && c <= 'F') return c - 'A' + 10;
            return -1;
        };
        int8_t h = nibble(hi), l = nibble(lo);
        if (h < 0 || l < 0) return false;
        out[i] = (uint8_t)((h << 4) | l);
    }
    return true;
}

// Hex-encode bytes to a lowercase hex string. buf must be 2*len+1 bytes.
static void hexEncode(const uint8_t* data, size_t len, char* buf) {
    static const char HEX_CHARS[] = "0123456789abcdef";
    for (size_t i = 0; i < len; i++) {
        buf[i * 2]     = HEX_CHARS[data[i] >> 4];
        buf[i * 2 + 1] = HEX_CHARS[data[i] & 0x0F];
    }
    buf[len * 2] = '\0';
}

// Standard Base64 encoding (RFC 4648). out must be ceil(len*4/3)+padding+1 bytes.
static void base64Encode(const uint8_t* in, size_t in_len, char* out) {
    static const char B64[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t o = 0;
    for (size_t i = 0; i < in_len; ) {
        uint32_t group = 0;
        int pad = 0;
        for (int j = 0; j < 3; j++) {
            group <<= 8;
            if (i < in_len) { group |= in[i++]; }
            else             { pad++;             }
        }
        out[o++] = B64[(group >> 18) & 0x3F];
        out[o++] = B64[(group >> 12) & 0x3F];
        out[o++] = (pad >= 2) ? '=' : B64[(group >> 6) & 0x3F];
        out[o++] = (pad >= 1) ? '=' : B64[(group)      & 0x3F];
    }
    out[o] = '\0';
}

// Base32 encoding (Crockford). out must be at least (in_len*8+4)/5+1 bytes.
// Used for did:key multibase encoding of public keys.
static void base32Encode(const uint8_t* in, size_t in_len, char* out) {
    static const char B32[] = "abcdefghijklmnopqrstuvwxyz234567";
    size_t o = 0;
    uint32_t buffer = 0;
    int bits = 0;
    for (size_t i = 0; i < in_len; i++) {
        buffer = (buffer << 8) | in[i];
        bits += 8;
        while (bits >= 5) {
            out[o++] = B32[(buffer >> (bits - 5)) & 0x1F];
            bits -= 5;
        }
    }
    if (bits > 0) {
        out[o++] = B32[(buffer << (5 - bits)) & 0x1F];
    }
    out[o] = '\0';
}

// Derive did:key from device public key.
// Format: did:key:z{base32(0x12 0x20 || 64-byte pubkey)}
// Returns length of DID string, or 0 on error.
static size_t deriveDID(const uint8_t pubkey[HL_PUBKEY_LEN], char did_out[HL_DID_MAX_LEN]) {
    // Multicodec prefix: 0x12 0x20 for secp256r1 (P-256)
    uint8_t payload[2 + HL_PUBKEY_LEN];
    payload[0] = 0x12;
    payload[1] = 0x20;
    memcpy(payload + 2, pubkey, HL_PUBKEY_LEN);

    char b32_buf[128];
    base32Encode(payload, sizeof(payload), b32_buf);

    // Format: did:key:z<base32>
    size_t len = snprintf(did_out, HL_DID_MAX_LEN, "did:key:z%s", b32_buf);
    return (len < HL_DID_MAX_LEN) ? len : 0;
}

// Simple SHA-256 block implementation (no external library dependency).
// Needed to build signedHash on-device.
// Reference: FIPS 180-4.
static void sha256(const uint8_t* data, size_t len, uint8_t digest[32]) {
    static const uint32_t K[64] = {
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,
        0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
        0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
        0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,
        0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
        0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
        0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,
        0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
        0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    };

    uint32_t h[8] = {
        0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
        0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19
    };

    auto rotr = [](uint32_t x, int n) { return (x >> n) | (x << (32 - n)); };

    // Pre-processing: message + padding
    size_t   bit_len  = len * 8;
    size_t   padded   = ((len + 8) / 64 + 1) * 64;
    uint8_t* msg      = (uint8_t*)calloc(padded, 1);
    if (!msg) return;  // OOM guard
    memcpy(msg, data, len);
    msg[len] = 0x80;
    // Big-endian 64-bit length at end
    for (int i = 0; i < 8; i++) {
        msg[padded - 8 + i] = (uint8_t)((uint64_t)bit_len >> (56 - i * 8));
    }

    for (size_t blk = 0; blk < padded / 64; blk++) {
        uint32_t w[64];
        const uint8_t* b = msg + blk * 64;
        for (int i = 0; i < 16; i++) {
            w[i] = ((uint32_t)b[i*4]<<24)|((uint32_t)b[i*4+1]<<16)|
                   ((uint32_t)b[i*4+2]<<8)|b[i*4+3];
        }
        for (int i = 16; i < 64; i++) {
            uint32_t s0 = rotr(w[i-15],7)  ^ rotr(w[i-15],18) ^ (w[i-15]>>3);
            uint32_t s1 = rotr(w[i-2], 17) ^ rotr(w[i-2], 19) ^ (w[i-2]>>10);
            w[i] = w[i-16] + s0 + w[i-7] + s1;
        }
        uint32_t a=h[0],b2=h[1],c=h[2],d=h[3],
                 e=h[4],f=h[5],g=h[6],hh=h[7];
        for (int i = 0; i < 64; i++) {
            uint32_t S1  = rotr(e,6) ^ rotr(e,11) ^ rotr(e,25);
            uint32_t ch  = (e & f) ^ (~e & g);
            uint32_t T1  = hh + S1 + ch + K[i] + w[i];
            uint32_t S0  = rotr(a,2) ^ rotr(a,13) ^ rotr(a,22);
            uint32_t maj = (a & b2) ^ (a & c) ^ (b2 & c);
            uint32_t T2  = S0 + maj;
            hh=g; g=f; f=e; e=d+T1;
            d=c; c=b2; b2=a; a=T1+T2;
        }
        h[0]+=a; h[1]+=b2; h[2]+=c; h[3]+=d;
        h[4]+=e; h[5]+=f;  h[6]+=g; h[7]+=hh;
    }
    free(msg);
    for (int i = 0; i < 8; i++) {
        digest[i*4]   = h[i] >> 24;
        digest[i*4+1] = h[i] >> 16;
        digest[i*4+2] = h[i] >> 8;
        digest[i*4+3] = h[i];
    }
}

// ── Send error response ────────────────────────────────────────────────────
static void sendError(int code, const char* msg) {
    JsonDocument doc;
    doc["status"] = "err";
    doc["code"]   = code;
    doc["msg"]    = msg;
    serializeJson(doc, Serial);
    Serial.println();
}

// ── Send status notification ──────────────────────────────────────────────
static void sendStatus(const char* event, const char* message) {
    JsonDocument doc;
    doc["event"] = event;
    doc["message"] = message;
    doc["protocol"] = PROTOCOL_VERSION;
    serializeJson(doc, Serial);
    Serial.println();
}

// ── Hardware diagnostic test ──────────────────────────────────────────────
static void runDiagnostics() {
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println("[HumanLink] HARDWARE DIAGNOSTICS");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    // Test JM-101
    Serial.println();
    Serial.println("1. Testing JM-101 Fingerprint Sensor:");
    Serial.printf("   Pins: RX=GPIO%d, TX=GPIO%d\\n", JM101_RX_PIN, JM101_TX_PIN);
    bool jm101_ok = sensor.begin();
    if (jm101_ok) {
        int templates = sensor.validTemplateCount();
        Serial.printf("   ✓ JM-101 responding, %d templates enrolled\\n", templates);
    } else {
        Serial.println("   ✗ JM-101 not responding");
    }

    Serial.println();
    Serial.println("2. Testing ATECC608A Secure Element:");
    Serial.println("   Pins: SDA=GPIO21, SCL=GPIO22");

    // Reinitialize to get fresh status
    bool atecc_ok = se.begin();
    if (atecc_ok) {
        Serial.printf("   ✓ ATECC608A responding, provisioned=%s, locked=%s\\n",
                     se.isProvisioned() ? "true" : "false",
                     se.isLocked() ? "true" : "false");
    } else {
        Serial.println("   ✗ ATECC608A not responding");
    }

    Serial.println();
    Serial.println("3. Overall Status:");
    if (jm101_ok && atecc_ok) {
        Serial.println("   ✓ All hardware components detected");
        Serial.println("   Ready for initialization");
    } else {
        Serial.println("   ✗ Hardware issues detected");
        Serial.println("   Please check connections and power supply");
    }

    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
}

// ── Auto-initialization flow ──────────────────────────────────────────────
static bool runAutoInitialization() {
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println("[HumanLink] FIRST BOOT DETECTED");
    Serial.println("[HumanLink] Starting auto-initialization...");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    // Check if ATECC608A needs provisioning
    if (!se.isProvisioned() || !se.isLocked()) {
        Serial.println("[HumanLink] ATECC608A needs provisioning...");
        sendStatus("initializing", "Configuring secure element...");

        if (!se.begin()) {
            Serial.println("[HumanLink] ERROR: ATECC608A initialization failed");
            sendStatus("init_error", "Secure element initialization failed");
            return false;
        }
        Serial.println("[HumanLink] ATECC608A provisioned successfully");
    }

    // Check if fingerprints need enrollment
    int enrolled = sensor.validTemplateCount();
    if (enrolled < MIN_REQUIRED_FINGERPRINTS) {
        Serial.printf("[HumanLink] Need to enroll %d fingerprint(s)\n", MIN_REQUIRED_FINGERPRINTS - enrolled);
        sendStatus("enrolling", "Please enroll your fingerprints");

        for (int slot = 1; slot <= MIN_REQUIRED_FINGERPRINTS; slot++) {
            Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Serial.printf("[HumanLink] Enrolling fingerprint %d/%d\n", slot, MIN_REQUIRED_FINGERPRINTS);
            Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

            char msg[64];
            snprintf(msg, sizeof(msg), "Enrolling fingerprint %d/%d", slot, MIN_REQUIRED_FINGERPRINTS);
            sendStatus("enrolling", msg);

            int attempts = 0;
            while (attempts < MAX_ENROLLMENT_ATTEMPTS) {
                int r = sensor.enrollFingerprint(slot, 30000);
                if (r == HL_OK) {
                    Serial.printf("[HumanLink] Fingerprint %d enrolled successfully\n", slot);
                    break;
                } else if (r == HL_ERR_TIMEOUT) {
                    Serial.println("[HumanLink] Enrollment timeout, trying again...");
                    attempts++;
                } else {
                    Serial.printf("[HumanLink] Enrollment failed (error %d), trying again...\n", r);
                    attempts++;
                }

                if (attempts >= MAX_ENROLLMENT_ATTEMPTS) {
                    Serial.printf("[HumanLink] Failed to enroll fingerprint %d after %d attempts\n", slot, MAX_ENROLLMENT_ATTEMPTS);
                    sendStatus("init_error", "Fingerprint enrollment failed");
                    return false;
                }
            }
        }
    }

    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.println("[HumanLink] INITIALIZATION COMPLETE");
    Serial.printf("[HumanLink] Device ready with %d enrolled fingerprint(s)\n", sensor.validTemplateCount());
    Serial.println("[HumanLink] You can now use authentication commands");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    sendStatus("ready", "Device initialization complete");
    return true;
}

// ── Core authorization flow ────────────────────────────────────────────────
static void runAuth(const uint8_t h_doc[HL_H_DOC_LEN], const uint8_t nonce[HL_NONCE_LEN],
                    const HL_DisplayInfo& display) {
    // 1. Show action to user
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.printf("[HumanLink] Action : %s\n", display.title);
    Serial.printf("[HumanLink] Risk   : %s\n", display.risk);
    Serial.println("[HumanLink] Place finger on sensor to authorize...");
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    // 2. Fetch sensor serial (before fingerprint — independent operation)
    uint8_t sensor_sn[HL_SENSOR_SERIAL_LEN] = {};
    int r = sensor.getChipSN(sensor_sn);
    if (r != HL_OK) {
        sendError(HL_ERR_SENSOR, "sensor serial read failed");
        return;
    }

    // 3. Check templates registered
    int tmpl_count = sensor.validTemplateCount();
    if (tmpl_count == 0) {
        sendError(HL_ERR_NOT_ENROLLED, "no fingerprint templates enrolled");
        return;
    }

    // 4. Fingerprint authentication
    uint16_t matched_id = 0, score = 0;
    r = sensor.autoIdentify(AUTH_TIMEOUT_MS, matched_id, score);
    if (r == HL_ERR_TIMEOUT) {
        sendError(HL_ERR_TIMEOUT, "fingerprint timeout");
        return;
    }
    if (r == HL_ERR_NO_MATCH) {
        sendError(HL_ERR_NO_MATCH, "fingerprint no match");
        return;
    }
    if (r != HL_OK) {
        sendError(HL_ERR_SENSOR, "fingerprint sensor error");
        return;
    }
    Serial.printf("[HumanLink] Fingerprint matched: slot=%u score=%u\n", matched_id, score);

    // 5. Build signedHash = SHA-256(matched_id_BE(2) ‖ score_BE(2) ‖ sensor_sn(32) ‖ nonce(8) ‖ h_doc(32))
    // Nonce is included for replay protection and challenge binding
    uint8_t payload_buf[2 + 2 + HL_SENSOR_SERIAL_LEN + HL_NONCE_LEN + HL_H_DOC_LEN];
    payload_buf[0] = (uint8_t)(matched_id >> 8);
    payload_buf[1] = (uint8_t)(matched_id & 0xFF);
    payload_buf[2] = (uint8_t)(score >> 8);
    payload_buf[3] = (uint8_t)(score & 0xFF);
    memcpy(payload_buf + 4,                              sensor_sn, HL_SENSOR_SERIAL_LEN);
    memcpy(payload_buf + 4 + HL_SENSOR_SERIAL_LEN,      nonce,     HL_NONCE_LEN);
    memcpy(payload_buf + 4 + HL_SENSOR_SERIAL_LEN + HL_NONCE_LEN, h_doc, HL_H_DOC_LEN);

    uint8_t signed_hash[32];
    sha256(payload_buf, sizeof(payload_buf), signed_hash);

    // 6. ATECC608A sign
    uint8_t sig[HL_SIG_LEN]    = {};
    uint8_t pubkey[HL_PUBKEY_LEN] = {};

    r = se.sign(signed_hash, sig);
    if (r != HL_OK) {
        sendError(r, "signing failed");
        return;
    }
    r = se.getPublicKey(pubkey);
    if (r != HL_OK) {
        sendError(r, "pubkey read failed");
        return;
    }

    // 7. Encode and emit JSON response
    char sn_hex[HL_SENSOR_SERIAL_LEN * 2 + 1];
    hexEncode(sensor_sn, HL_SENSOR_SERIAL_LEN, sn_hex);

    char nonce_hex[HL_NONCE_LEN * 2 + 1];
    hexEncode(nonce, HL_NONCE_LEN, nonce_hex);

    char sig_b64[HL_SIG_LEN * 2 + 4];       // upper bound for base64
    base64Encode(sig, HL_SIG_LEN, sig_b64);

    char pubkey_b64[HL_PUBKEY_LEN * 2 + 4];
    base64Encode(pubkey, HL_PUBKEY_LEN, pubkey_b64);

    char hash_hex[32 * 2 + 1];
    hexEncode(signed_hash, 32, hash_hex);

    JsonDocument doc;
    doc["status"]         = "ok";
    doc["protocol"]       = PROTOCOL_VERSION;
    doc["matched_id"]     = matched_id;
    doc["score"]          = score;
    doc["sensor_serial"]  = sn_hex;
    doc["nonce"]          = nonce_hex;        // Echo nonce for replay protection
    doc["signed_hash"]    = hash_hex;         // Let PC SDK verify SHA-256 rebuild
    doc["sig"]            = sig_b64;
    doc["pubkey"]         = pubkey_b64;

    serializeJson(doc, Serial);
    Serial.println();

    Serial.println("[HumanLink] Authorization complete.");
}

// ── setup ──────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);

    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
    Serial.printf("[HumanLink] Firmware v%s starting\n", PROTOCOL_VERSION);
    Serial.println("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

    // Init JM-101 on Serial2
    Serial.println("[HumanLink] Initializing JM-101 fingerprint sensor...");
    Serial.printf("[HumanLink] JM-101 pins: RX=GPIO%d, TX=GPIO%d\n", JM101_RX_PIN, JM101_TX_PIN);
    Serial2.begin(57600, SERIAL_8N2, JM101_RX_PIN, JM101_TX_PIN);
    if (!sensor.begin()) {
        Serial.println("[HumanLink] ERROR: JM-101 sensor init failed");
        Serial.println("[HumanLink] Please check:");
        Serial.println("[HumanLink]   - JM-101 power supply (3.3V or 5V)");
        Serial.println("[HumanLink]   - UART connections: RX->GPIO16, TX->GPIO17");
        Serial.println("[HumanLink]   - Ground connection");
        // Continue — will report per-auth
    } else {
        Serial.println("[HumanLink] JM-101 sensor connected successfully");
    }

    // Init ATECC608A
    Serial.println("[HumanLink] Initializing ATECC608A secure element...");
    Serial.println("[HumanLink] I2C pins: SDA=GPIO21, SCL=GPIO22");
    if (!se.begin()) {
        Serial.println("[HumanLink] ERROR: ATECC608A secure element init failed");
        Serial.println("[HumanLink] Please check:");
        Serial.println("[HumanLink]   - ATECC608A power supply (3.3V)");
        Serial.println("[HumanLink]   - I2C connections: SDA->GPIO21, SCL->GPIO22");
        Serial.println("[HumanLink]   - I2C pull-up resistors (4.7kΩ)");
        Serial.println("[HumanLink]   - Ground connection");
        // Continue — will report per-auth
    } else {
        Serial.println("[HumanLink] ATECC608A connected successfully");
    }

    // Check if auto-initialization is needed
    bool needs_init = false;
    if (!se.isProvisioned() || !se.isLocked()) {
        needs_init = true;
    } else if (sensor.validTemplateCount() < MIN_REQUIRED_FINGERPRINTS) {
        needs_init = true;
    }

    if (needs_init) {
        if (runAutoInitialization()) {
            state = State::IDLE;
        } else {
            Serial.println("[HumanLink] Initialization failed, device not ready");
            // Stay in INITIALIZING state to allow retry
            return;  // Exit setup, will retry in loop
        }
    } else {
        Serial.println("[HumanLink] Device already initialized");
        state = State::IDLE;
    }

    // Derive device DID from public key
    uint8_t pubkey[HL_PUBKEY_LEN];
    if (se.getPublicKey(pubkey) == HL_OK) {
        deriveDID(pubkey, device_did);
        Serial.printf("[HumanLink] Device DID: %s\n", device_did);
    } else {
        Serial.println("[HumanLink] WARNING: Could not derive device DID");
        strncpy(device_did, "did:key:unknown", sizeof(device_did) - 1);
    }

    // Emit device ready signal (PC SDK polls this)
    if (state == State::IDLE) {
        JsonDocument ready;
        ready["event"]       = "ready";
        ready["protocol"]    = PROTOCOL_VERSION;
        ready["device_did"]  = device_did;  // Auto-export DID for on-chain registration
        ready["enrolled"]    = sensor.validTemplateCount();
        serializeJson(ready, Serial);
        Serial.println();
    } else {
        JsonDocument init_needed;
        init_needed["event"]    = "init_required";
        init_needed["protocol"] = PROTOCOL_VERSION;
        init_needed["message"]  = "Device requires initialization - use 'init' command";
        serializeJson(init_needed, Serial);
        Serial.println();
    }
}

// ── loop ───────────────────────────────────────────────────────────────────
static char line_buf[512];
static int  line_len = 0;

void loop() {
    // Accumulate incoming bytes until newline
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (line_len == 0) continue;
            line_buf[line_len] = '\0';

            // Parse JSON command
            JsonDocument cmd;
            DeserializationError err = deserializeJson(cmd, line_buf, line_len);
            line_len = 0;

            if (err) {
                sendError(HL_ERR_BAD_INPUT, "json parse error");
                continue;
            }

            const char* cmd_str = cmd["cmd"];
            if (!cmd_str) {
                sendError(HL_ERR_BAD_INPUT, "missing cmd field");
                continue;
            }

            // ── "auth" command ─────────────────────────────────────────────
            if (strcmp(cmd_str, "auth") == 0) {
                if (state == State::INITIALIZING) {
                    sendError(HL_ERR_BAD_INPUT, "device not ready, initialization required");
                    continue;
                }
                if (state == State::AUTHORIZING) {
                    sendError(HL_ERR_BAD_INPUT, "auth already in progress");
                    continue;
                }
                if (state == State::ENROLLING) {
                    sendError(HL_ERR_BAD_INPUT, "enrollment in progress");
                    continue;
                }

                const char* h_doc_hex = cmd["h_doc"];
                if (!h_doc_hex) {
                    sendError(HL_ERR_BAD_INPUT, "missing h_doc");
                    continue;
                }

                uint8_t h_doc[HL_H_DOC_LEN];
                if (!hexDecode(h_doc_hex, h_doc, HL_H_DOC_LEN)) {
                    sendError(HL_ERR_BAD_INPUT, "h_doc must be 64 hex chars (32 bytes)");
                    continue;
                }

                const char* nonce_hex = cmd["nonce"];
                if (!nonce_hex) {
                    sendError(HL_ERR_BAD_INPUT, "missing nonce");
                    continue;
                }

                uint8_t nonce[HL_NONCE_LEN];
                if (!hexDecode(nonce_hex, nonce, HL_NONCE_LEN)) {
                    sendError(HL_ERR_BAD_INPUT, "nonce must be 16 hex chars (8 bytes)");
                    continue;
                }

                HL_DisplayInfo display = {};
                const char* title = cmd["display"]["title"] | "Unknown action";
                const char* risk  = cmd["display"]["risk"]  | "unknown";
                strncpy(display.title, title, sizeof(display.title) - 1);
                strncpy(display.risk,  risk,  sizeof(display.risk)  - 1);

                state = State::AUTHORIZING;
                runAuth(h_doc, nonce, display);
                state = State::IDLE;

            // ── "status" command ───────────────────────────────────────────
            } else if (strcmp(cmd_str, "status") == 0) {
                JsonDocument resp;
                resp["status"]       = "ok";
                const char* state_str = "unknown";
                switch (state) {
                    case State::INITIALIZING: state_str = "initializing"; break;
                    case State::IDLE:         state_str = "idle"; break;
                    case State::AUTHORIZING:  state_str = "authorizing"; break;
                    case State::ENROLLING:    state_str = "enrolling"; break;
                }
                resp["state"]        = state_str;
                resp["provisioned"]  = se.isProvisioned();
                resp["enrolled"]     = sensor.validTemplateCount();
                resp["protocol"]     = PROTOCOL_VERSION;
                resp["device_did"]   = device_did;  // For SDK to query DID
                resp["needs_init"]   = (state == State::INITIALIZING);
                serializeJson(resp, Serial);
                Serial.println();

            // ── "getDID" command ───────────────────────────────────────────
            } else if (strcmp(cmd_str, "getDID") == 0) {
                JsonDocument resp;
                resp["status"]     = "ok";
                resp["device_did"] = device_did;
                resp["protocol"]   = PROTOCOL_VERSION;
                serializeJson(resp, Serial);
                Serial.println();

            // ── "cancel" command ───────────────────────────────────────────
            } else if (strcmp(cmd_str, "cancel") == 0) {
                sensor.cancel();
                if (state == State::AUTHORIZING || state == State::ENROLLING) {
                    state = State::IDLE;
                }
                JsonDocument resp;
                resp["status"] = "ok";
                resp["msg"]    = "cancelled";
                serializeJson(resp, Serial);
                Serial.println();

            // ── "init" command ─────────────────────────────────────────────
            } else if (strcmp(cmd_str, "init") == 0) {
                if (state != State::IDLE && state != State::INITIALIZING) {
                    sendError(HL_ERR_BAD_INPUT, "cannot init while busy");
                    continue;
                }

                Serial.println("[HumanLink] Manual initialization requested");
                state = State::INITIALIZING;
                if (runAutoInitialization()) {
                    state = State::IDLE;
                    JsonDocument resp;
                    resp["status"] = "ok";
                    resp["msg"] = "initialization complete";
                    serializeJson(resp, Serial);
                    Serial.println();
                } else {
                    JsonDocument resp;
                    resp["status"] = "err";
                    resp["code"] = HL_ERR_SENSOR;
                    resp["msg"] = "initialization failed";
                    serializeJson(resp, Serial);
                    Serial.println();
                }

            // ── "diag" command ─────────────────────────────────────────────
            } else if (strcmp(cmd_str, "diag") == 0) {
                runDiagnostics();
                JsonDocument resp;
                resp["status"] = "ok";
                resp["msg"] = "diagnostics complete";
                serializeJson(resp, Serial);
                Serial.println();

            } else {
                sendError(HL_ERR_BAD_INPUT, "unknown cmd");
            }

        } else {
            if (line_len < (int)sizeof(line_buf) - 1) {
                line_buf[line_len++] = c;
            }
        }
    }
}
