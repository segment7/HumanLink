/**
 * JM-101 / FPM383C Fingerprint Sensor Driver
 *
 * Protocol: UART 57600bps 8N2
 * Commands used:
 *   PS_AutoIdentify (0x32) — collect + feature + search, returns matched_id + score
 *   GetChipSN (0x34)       — 32-byte unique serial for signature binding
 *   PS_ValidTempleteNum (0x1D) — query enrolled count
 *   PS_Cancel (0x30)       — abort ongoing collection
 *
 * Packet format (JM-101 spec §3.2):
 *   Header  : 0xEF01 (2 bytes)
 *   Addr    : 0xFFFFFFFF (4 bytes, broadcast)
 *   PID     : 0x01 command / 0x07 response (1 byte)
 *   Length  : payload + checksum length (2 bytes, big-endian)
 *   Payload : command code + params
 *   Checksum: sum of PID+Length+Payload bytes (2 bytes)
 */

#pragma once

#include <Arduino.h>
#include <Adafruit_Fingerprint.h>
#include "protocol.h"

#define FINGERPRINT_GETCHIPSN 0x34
#define FINGERPRINT_CANCEL_CMD 0x30

class JM101 {
public:
    /**
     * @param serial  HardwareSerial instance wired to sensor TX/RX
     * @param baud    Sensor baud rate (default 57600)
     */
    explicit JM101(HardwareSerial& serial, uint32_t baud = 57600);

    /**
     * Initialize UART. Returns true when sensor responds to handshake.
     */
    bool begin();

    /**
     * Run AutoIdentify: capture fingerprint and search all templates.
     * Blocks until finger placed or timeout.
     *
     * @param timeout_ms  Max wait for finger (ms)
     * @param matched_id  [out] Slot index on success
     * @param score       [out] Match confidence score
     * @return HL_OK, HL_ERR_TIMEOUT, HL_ERR_NO_MATCH, HL_ERR_SENSOR, HL_ERR_NOT_ENROLLED
     */
    int autoIdentify(uint32_t timeout_ms, uint16_t& matched_id, uint16_t& score);

    /**
     * Read chip serial number (32 bytes) for signature binding.
     * @return HL_OK or HL_ERR_SENSOR
     */
    int getChipSN(uint8_t sn[HL_SENSOR_SERIAL_LEN]);

    /**
     * Return number of enrolled templates (0 = nothing registered).
     */
    int validTemplateCount();

    /**
     * Abort any ongoing fingerprint collection.
     */
    void cancel();

    /**
     * Enroll a new fingerprint template.
     * @param slot_id  Template slot to store (1-200)
     * @param timeout_ms Max 20s wait time for finger placement
     * @return HL_OK on success, HL_ERR_* on failure
     */
    int enrollFingerprint(uint16_t slot_id, uint32_t timeout_ms = 20000);

private:
    Adafruit_Fingerprint _fingerprint;
    uint32_t            _baud;

    int _captureAndGenerate(uint8_t buffer_id, uint32_t timeout_ms);
};
