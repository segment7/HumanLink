/**
 * JM-101 Fingerprint Sensor Driver Implementation
 *
 * Uses Adafruit Fingerprint Sensor Library for AS608-compatible packet handling
 * and fingerprint operations.
 */

#include "jm101.h"

// ── Constructor ────────────────────────────────────────────────────────────
JM101::JM101(HardwareSerial& serial, uint32_t baud)
    : _fingerprint(&serial), _baud(baud) {}

// ── begin ──────────────────────────────────────────────────────────────────
bool JM101::begin() {
    _fingerprint.begin(_baud);
    delay(500);  // Give sensor more time to initialize

    Serial.println("[JM101] Probing fingerprint sensor...");

    for (int attempt = 1; attempt <= 3; attempt++) {
        Serial.printf("[JM101] Probe attempt %d/3\n", attempt);

        if (_fingerprint.verifyPassword() && _fingerprint.getTemplateCount() == FINGERPRINT_OK) {
            Serial.printf("[JM101] Sensor responded successfully, %u templates enrolled\n",
                          _fingerprint.templateCount);
            _fingerprint.setSecurityLevel(FINGERPRINT_SECURITY_LEVEL_3);
            _fingerprint.setPacketSize(FINGERPRINT_PACKET_SIZE_64);
            return true;
        }

        Serial.printf("[JM101] Attempt %d failed, retrying...\n", attempt);
        delay(500);
    }

    Serial.println("[JM101] All probe attempts failed");
    Serial.println("[JM101] Check UART connections and power supply");
    return false;
}

// ── autoIdentify ──────────────────────────────────────────────────────────
int JM101::autoIdentify(uint32_t timeout_ms, uint16_t& matched_id, uint16_t& score) {
    uint32_t deadline = millis() + timeout_ms;

    while (millis() < deadline) {
        uint8_t p = _fingerprint.getImage();
        if (p == FINGERPRINT_OK) {
            uint8_t r = _fingerprint.image2Tz(1);
            if (r != FINGERPRINT_OK) {
                Serial.printf("[JM101] image2Tz error=0x%02X\n", r);
                return HL_ERR_SENSOR;
            }

            r = _fingerprint.fingerFastSearch();
            if (r == FINGERPRINT_OK) {
                matched_id = _fingerprint.fingerID;
                score = _fingerprint.confidence;
                return HL_OK;
            }
            if (r == FINGERPRINT_NOTFOUND) {
                return HL_ERR_NO_MATCH;
            }
            Serial.printf("[JM101] fingerFastSearch error=0x%02X\n", r);
            return HL_ERR_SENSOR;
        }

        if (p == FINGERPRINT_NOFINGER) {
            continue;
        }
        if (p == FINGERPRINT_IMAGEFAIL || p == FINGERPRINT_IMAGEMESS ||
            p == FINGERPRINT_FEATUREFAIL || p == FINGERPRINT_INVALIDIMAGE) {
            continue;
        }

        Serial.printf("[JM101] getImage error=0x%02X\n", p);
        return HL_ERR_SENSOR;
    }

    return HL_ERR_TIMEOUT;
}

// ── getChipSN ─────────────────────────────────────────────────────────────
int JM101::getChipSN(uint8_t sn[HL_SENSOR_SERIAL_LEN]) {
    uint8_t cmd[] = {FINGERPRINT_GETCHIPSN};
    Adafruit_Fingerprint_Packet packet(FINGERPRINT_COMMANDPACKET, 1, cmd);
    _fingerprint.writeStructuredPacket(packet);

    if (_fingerprint.getStructuredPacket(&packet, 2000) != FINGERPRINT_OK) {
        return HL_ERR_SENSOR;
    }
    if (packet.type != FINGERPRINT_ACKPACKET) {
        return HL_ERR_SENSOR;
    }
    if (packet.data[0] != FINGERPRINT_OK) {
        return HL_ERR_SENSOR;
    }

    uint16_t payload_len = packet.length - 2;
    if (payload_len < 33) {
        return HL_ERR_SENSOR;
    }

    memcpy(sn, packet.data + 1, HL_SENSOR_SERIAL_LEN);
    return HL_OK;
}

// ── validTemplateCount ────────────────────────────────────────────────────
int JM101::validTemplateCount() {
    if (_fingerprint.getTemplateCount() != FINGERPRINT_OK) {
        return -1;
    }
    return _fingerprint.templateCount;
}

// ── cancel ────────────────────────────────────────────────────────────────
void JM101::cancel() {
    uint8_t cmd[] = {FINGERPRINT_CANCEL_CMD};
    Adafruit_Fingerprint_Packet packet(FINGERPRINT_COMMANDPACKET, 1, cmd);
    _fingerprint.writeStructuredPacket(packet);
}

// ── enrollFingerprint ─────────────────────────────────────────────────────
int JM101::enrollFingerprint(uint16_t slot_id, uint32_t timeout_ms) {
    Serial.printf("[JM101] Enrolling fingerprint to slot %u...\n", slot_id);

    uint32_t deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        uint8_t p = _fingerprint.getImage();
        if (p == FINGERPRINT_OK) {
            break;
        }
        if (p == FINGERPRINT_NOFINGER) {
            continue;
        }
        if (p == FINGERPRINT_IMAGEFAIL || p == FINGERPRINT_IMAGEMESS ||
            p == FINGERPRINT_FEATUREFAIL || p == FINGERPRINT_INVALIDIMAGE) {
            continue;
        }
        Serial.printf("[JM101] getImage error=0x%02X\n", p);
        return HL_ERR_SENSOR;
    }
    if (millis() >= deadline) {
        return HL_ERR_TIMEOUT;
    }

    if (_fingerprint.image2Tz(1) != FINGERPRINT_OK) {
        Serial.println("[JM101] Character generation failed on first capture");
        return HL_ERR_SENSOR;
    }

    Serial.println("[JM101] Remove finger and place again for second capture...");
    delay(1000);
    deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        uint8_t p = _fingerprint.getImage();
        if (p == FINGERPRINT_OK) {
            break;
        }
        if (p == FINGERPRINT_NOFINGER) {
            continue;
        }
        if (p == FINGERPRINT_IMAGEFAIL || p == FINGERPRINT_IMAGEMESS ||
            p == FINGERPRINT_FEATUREFAIL || p == FINGERPRINT_INVALIDIMAGE) {
            continue;
        }
        Serial.printf("[JM101] getImage error=0x%02X\n", p);
        return HL_ERR_SENSOR;
    }
    if (millis() >= deadline) {
        return HL_ERR_TIMEOUT;
    }

    if (_fingerprint.image2Tz(2) != FINGERPRINT_OK) {
        Serial.println("[JM101] Character generation failed on second capture");
        return HL_ERR_SENSOR;
    }

    if (_fingerprint.createModel() != FINGERPRINT_OK) {
        Serial.println("[JM101] Template creation failed");
        return HL_ERR_SENSOR;
    }

    if (_fingerprint.storeModel(slot_id) != FINGERPRINT_OK) {
        Serial.println("[JM101] Template storage failed");
        return HL_ERR_SENSOR;
    }

    Serial.printf("[JM101] Fingerprint enrolled successfully to slot %u\n", slot_id);
    return HL_OK;
}

// ── _captureAndGenerate ───────────────────────────────────────────────────
int JM101::_captureAndGenerate(uint8_t buffer_id, uint32_t timeout_ms) {
    uint32_t deadline = millis() + timeout_ms;
    while (millis() < deadline) {
        uint8_t p = _fingerprint.getImage();
        if (p == FINGERPRINT_OK) {
            if (_fingerprint.image2Tz(buffer_id + 1) == FINGERPRINT_OK) {
                return HL_OK;
            }
            Serial.println("[JM101] Character generation failed");
            return HL_ERR_SENSOR;
        }
        if (p == FINGERPRINT_NOFINGER) {
            continue;
        }
        if (p == FINGERPRINT_IMAGEFAIL || p == FINGERPRINT_IMAGEMESS ||
            p == FINGERPRINT_FEATUREFAIL || p == FINGERPRINT_INVALIDIMAGE) {
            continue;
        }
        Serial.printf("[JM101] getImage error=0x%02X\n", p);
        return HL_ERR_SENSOR;
    }
    return HL_ERR_TIMEOUT;
}
