/**
 * HumanLink Protocol v0.3 — Firmware-side structures
 *
 * Defines the H_doc (challenge hash) input format and the signed proof
 * output that the PC SDK uses to assemble HumanPresenceAssertion.
 *
 * USB Serial framing (newline-delimited JSON):
 *   PC → Device:  {"cmd":"auth","h_doc":"<hex64>","nonce":"<hex16>","display":{"title":"...","risk":"high"}}
 *   Device → PC:  {"status":"ok","matched_id":3,"score":188,"sensor_serial":"<hex32>","sig":"<base64>"}
 *   Device → PC:  {"status":"err","code":<int>,"msg":"..."}
 */

#pragma once

#include <stdint.h>

// ── Error codes ────────────────────────────────────────────────────────────
#define HL_OK                   0
#define HL_ERR_TIMEOUT          1   // Fingerprint not presented in time
#define HL_ERR_NO_MATCH         2   // Fingerprint did not match any template
#define HL_ERR_SENSOR           3   // JM-101 communication error
#define HL_ERR_SE               4   // ATECC608A communication error
#define HL_ERR_BAD_INPUT        5   // Malformed H_doc or command
#define HL_ERR_NOT_ENROLLED     6   // No templates registered
#define HL_ERR_SIGN_FAIL        7   // ECDSA signing failed

// ── Constants ──────────────────────────────────────────────────────────────
#define HL_H_DOC_LEN            32  // SHA-256 bytes
#define HL_SENSOR_SERIAL_LEN    32  // JM-101 chip SN bytes
#define HL_SIG_LEN              64  // ECDSA P-256 raw (r‖s) bytes
#define HL_PUBKEY_LEN           64  // Uncompressed P-256 (without 0x04 prefix)
#define HL_NONCE_LEN            8   // 8 random bytes from PC SDK
#define HL_DID_MAX_LEN          128 // did:key:z... max length

// ── Signed payload (what ATECC608A signs) ─────────────────────────────────
// signedHash = SHA-256( matched_id_u16 ‖ score_u16 ‖ sensor_serial[32] ‖ nonce[8] ‖ h_doc[32] )
// Includes nonce to bind signature to specific challenge (prevents replay attacks)
// Total: 2 + 2 + 32 + 8 + 32 = 76 bytes → digest is 32 bytes
typedef struct {
    uint16_t matched_id;                    // Fingerprint slot index (big-endian on wire)
    uint16_t score;                         // Match confidence score
    uint8_t  sensor_serial[HL_SENSOR_SERIAL_LEN];
    uint8_t  nonce[HL_NONCE_LEN];           // Replay protection
    uint8_t  h_doc[HL_H_DOC_LEN];
} HL_SignPayload;

// ── Auth result returned up the stack ─────────────────────────────────────
typedef struct {
    uint8_t  status;                        // HL_OK or HL_ERR_*
    uint16_t matched_id;
    uint16_t score;
    uint8_t  sensor_serial[HL_SENSOR_SERIAL_LEN];
    uint8_t  signature[HL_SIG_LEN];         // r‖s
    uint8_t  pubkey[HL_PUBKEY_LEN];         // device public key (for DID derivation)
} HL_AuthResult;

// ── Display info passed from PC SDK ───────────────────────────────────────
typedef struct {
    char title[64];
    char risk[8];   // "high" | "medium" | "low"
} HL_DisplayInfo;
