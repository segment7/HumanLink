/**
 * JM-101 Fingerprint Sensor Driver Implementation
 *
 * Real hardware path: full UART packet protocol per JM-101 spec.
 * Mock path (#define HUMANLINK_MOCK_HARDWARE): returns fixed test values
 *   so the full enclave state machine can be exercised without hardware.
 */

#include "jm101.h"

// ── Packet constants ───────────────────────────────────────────────────────
static const uint8_t  JM_HDR[]  = {0xEF, 0x01};
static const uint8_t  JM_ADDR[] = {0xFF, 0xFF, 0xFF, 0xFF};
static const uint8_t  PID_CMD   = 0x01;
static const uint8_t  PID_DATA  = 0x02;
static const uint8_t  PID_ACK   = 0x07;

// ── Command codes ──────────────────────────────────────────────────────────
static const uint8_t  CMD_AUTO_IDENTIFY   = 0x32;
static const uint8_t  CMD_GET_CHIP_SN     = 0x34;
static const uint8_t  CMD_VALID_TMPL_NUM  = 0x1D;
static const uint8_t  CMD_CANCEL          = 0x30;

// ── Confirmation codes ─────────────────────────────────────────────────────
static const uint8_t  CC_OK               = 0x00;
static const uint8_t  CC_NO_FINGER        = 0x02;
static const uint8_t  CC_NO_MATCH         = 0x09;
static const uint8_t  CC_NO_TEMPLATE      = 0x4B; // sensor-specific: empty DB

// ── Mock fingerprint slot / score returned in test mode ───────────────────
#ifdef HUMANLINK_MOCK_HARDWARE
static const uint16_t MOCK_MATCHED_ID = 1;
static const uint16_t MOCK_SCORE      = 188;
static const uint8_t  MOCK_SN[32]     = {
    0xDE,0xAD,0xBE,0xEF, 0xCA,0xFE,0xBA,0xBE,
    0x01,0x23,0x45,0x67, 0x89,0xAB,0xCD,0xEF,
    0xFE,0xDC,0xBA,0x98, 0x76,0x54,0x32,0x10,
    0x11,0x22,0x33,0x44, 0x55,0x66,0x77,0x88
};
#endif

// ── Constructor ────────────────────────────────────────────────────────────
JM101::JM101(HardwareSerial& serial, uint32_t baud)
    : _serial(serial), _baud(baud) {}

// ── begin ──────────────────────────────────────────────────────────────────
bool JM101::begin() {
#ifdef HUMANLINK_MOCK_HARDWARE
    Serial.println("[JM101] MOCK: sensor ready");
    return true;
#else
    _serial.begin(_baud, SERIAL_8N2);
    delay(200);

    // Probe: query template count; expect any valid ACK back
    uint8_t cmd[] = {CMD_VALID_TMPL_NUM};
    _sendPacket(PID_CMD, cmd, 1);

    uint8_t buf[32];
    uint16_t plen = 0;
    int r = _recvPacket(buf, sizeof(buf), plen, 1500);
    return (r == HL_OK);
#endif
}

// ── autoIdentify ──────────────────────────────────────────────────────────
int JM101::autoIdentify(uint32_t timeout_ms, uint16_t& matched_id, uint16_t& score) {
#ifdef HUMANLINK_MOCK_HARDWARE
    Serial.println("[JM101] MOCK: waiting for finger (2s simulated)...");
    delay(2000);
    matched_id = MOCK_MATCHED_ID;
    score      = MOCK_SCORE;
    Serial.printf("[JM101] MOCK: matched slot=%u score=%u\n", matched_id, score);
    return HL_OK;
#else
    // PS_AutoIdentify: cmd=0x32, SecurityLevel(2B) + MatchScore(2B) + FpgroupCnt(2B)
    // SecurityLevel 0x0003 = level 3; MatchScore 0x0064 = 100; FpGroupCnt 0x0001
    uint8_t cmd[] = {
        CMD_AUTO_IDENTIFY,
        0x00, 0x03,  // SecurityLevel
        0x00, 0x64,  // MatchScore minimum (100)
        0x00, 0x01   // FpGroupCnt
    };
    _sendPacket(PID_CMD, cmd, sizeof(cmd));

    uint32_t deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        uint8_t  buf[64];
        uint16_t plen = 0;
        int r = _recvPacket(buf, sizeof(buf), plen, 3000);
        if (r != HL_OK) continue;

        if (plen < 1) continue;
        uint8_t cc = buf[0];

        if (cc == CC_OK && plen >= 5) {
            // ACK: CC(1) + MatchedID(2) + Score(2)
            matched_id = ((uint16_t)buf[1] << 8) | buf[2];
            score      = ((uint16_t)buf[3] << 8) | buf[4];
            return HL_OK;
        }
        if (cc == CC_NO_FINGER) continue;  // Still waiting
        if (cc == CC_NO_MATCH)  return HL_ERR_NO_MATCH;
        if (cc == CC_NO_TEMPLATE) return HL_ERR_NOT_ENROLLED;
        // Other sensor errors
        Serial.printf("[JM101] autoIdentify cc=0x%02X\n", cc);
        return HL_ERR_SENSOR;
    }
    return HL_ERR_TIMEOUT;
#endif
}

// ── getChipSN ─────────────────────────────────────────────────────────────
int JM101::getChipSN(uint8_t sn[HL_SENSOR_SERIAL_LEN]) {
#ifdef HUMANLINK_MOCK_HARDWARE
    memcpy(sn, MOCK_SN, HL_SENSOR_SERIAL_LEN);
    return HL_OK;
#else
    uint8_t cmd[] = {CMD_GET_CHIP_SN};
    _sendPacket(PID_CMD, cmd, 1);

    uint8_t  buf[64];
    uint16_t plen = 0;
    int r = _recvPacket(buf, sizeof(buf), plen, 2000);
    if (r != HL_OK) return HL_ERR_SENSOR;
    if (plen < 33 || buf[0] != CC_OK) return HL_ERR_SENSOR;

    // ACK: CC(1) + SN(32)
    memcpy(sn, buf + 1, HL_SENSOR_SERIAL_LEN);
    return HL_OK;
#endif
}

// ── validTemplateCount ────────────────────────────────────────────────────
int JM101::validTemplateCount() {
#ifdef HUMANLINK_MOCK_HARDWARE
    return 3;  // Simulate 3 registered fingerprints
#else
    uint8_t cmd[] = {CMD_VALID_TMPL_NUM};
    _sendPacket(PID_CMD, cmd, 1);

    uint8_t  buf[16];
    uint16_t plen = 0;
    int r = _recvPacket(buf, sizeof(buf), plen, 2000);
    if (r != HL_OK || plen < 3 || buf[0] != CC_OK) return -1;

    return ((int)buf[1] << 8) | buf[2];
#endif
}

// ── cancel ────────────────────────────────────────────────────────────────
void JM101::cancel() {
#ifndef HUMANLINK_MOCK_HARDWARE
    uint8_t cmd[] = {CMD_CANCEL};
    _sendPacket(PID_CMD, cmd, 1);
#endif
}

// ── _sendPacket ───────────────────────────────────────────────────────────
void JM101::_sendPacket(uint8_t pid, const uint8_t* payload, uint16_t len) {
    // Length field = len + 2 (checksum)
    uint16_t length = len + 2;
    uint16_t chk    = _checksum(pid, payload, len);

    _serial.write(JM_HDR,  2);
    _serial.write(JM_ADDR, 4);
    _serial.write(pid);
    _serial.write((uint8_t)(length >> 8));
    _serial.write((uint8_t)(length & 0xFF));
    _serial.write(payload, len);
    _serial.write((uint8_t)(chk >> 8));
    _serial.write((uint8_t)(chk & 0xFF));
}

// ── _recvPacket ───────────────────────────────────────────────────────────
int JM101::_recvPacket(uint8_t* buf, uint16_t buflen, uint16_t& paylen, uint32_t timeout_ms) {
    uint32_t deadline = millis() + timeout_ms;
    uint8_t  hdr[9];  // EF01 + ADDR(4) + PID(1) + LEN(2)
    uint8_t  idx = 0;

    // Read header (9 bytes)
    while (idx < 9 && millis() < deadline) {
        if (_serial.available()) {
            hdr[idx++] = _serial.read();
        }
    }
    if (idx < 9) return HL_ERR_SENSOR;
    if (hdr[0] != 0xEF || hdr[1] != 0x01) return HL_ERR_SENSOR;

    uint8_t  pid    = hdr[6];
    uint16_t length = ((uint16_t)hdr[7] << 8) | hdr[8];
    if (length < 2) return HL_ERR_SENSOR;

    uint16_t data_len = length - 2;  // Subtract checksum
    if (data_len > buflen) return HL_ERR_SENSOR;

    // Read payload
    idx = 0;
    while (idx < data_len && millis() < deadline) {
        if (_serial.available()) buf[idx++] = _serial.read();
    }
    if (idx < data_len) return HL_ERR_SENSOR;

    // Read and verify checksum
    uint8_t cs[2];
    idx = 0;
    while (idx < 2 && millis() < deadline) {
        if (_serial.available()) cs[idx++] = _serial.read();
    }
    if (idx < 2) return HL_ERR_SENSOR;

    uint16_t expected = _checksum(pid, buf, data_len);
    uint16_t received = ((uint16_t)cs[0] << 8) | cs[1];
    if (expected != received) {
        Serial.printf("[JM101] checksum fail: exp=0x%04X got=0x%04X\n", expected, received);
        return HL_ERR_SENSOR;
    }

    paylen = data_len;
    return HL_OK;
}

// ── _checksum ─────────────────────────────────────────────────────────────
uint16_t JM101::_checksum(uint8_t pid, const uint8_t* data, uint16_t len) {
    // Sum of PID + Length bytes + payload bytes
    // Length = len + 2 (checksum itself not included in sum input)
    uint16_t length = len + 2;
    uint16_t sum    = (uint16_t)pid + (length >> 8) + (length & 0xFF);
    for (uint16_t i = 0; i < len; i++) sum += data[i];
    return sum;
}
