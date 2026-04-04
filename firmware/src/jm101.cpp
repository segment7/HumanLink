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
    const int NUM_VERIFICATION_READS = 3;  // Verify with multiple reads
    const int MIN_CONFIDENCE_THRESHOLD = 80;  // Minimum confidence for each read
    const uint32_t SINGLE_READ_TIMEOUT = timeout_ms / 6;  // Allocate time for retries

    struct MatchResult {
        uint16_t id;
        uint16_t confidence;
        bool valid;
    };

    MatchResult matches[NUM_VERIFICATION_READS];
    int successful_matches = 0;

    Serial.printf("[JM101] Authentication with %d verification reads (threshold: %d)\n",
                  NUM_VERIFICATION_READS, MIN_CONFIDENCE_THRESHOLD);

    uint32_t global_deadline = millis() + timeout_ms;

    for (int attempt = 0; attempt < NUM_VERIFICATION_READS && millis() < global_deadline; attempt++) {
        Serial.printf("[JM101] Verification read %d/%d...\n", attempt + 1, NUM_VERIFICATION_READS);

        uint32_t read_deadline = millis() + SINGLE_READ_TIMEOUT;
        bool read_successful = false;

        // Try to get a good image for this verification read
        while (millis() < read_deadline && millis() < global_deadline) {
            uint8_t p = _fingerprint.getImage();
            if (p == FINGERPRINT_OK) {
                uint8_t r = _fingerprint.image2Tz(1);
                if (r != FINGERPRINT_OK) {
                    Serial.printf("[JM101] image2Tz error=0x%02X on read %d\n", r, attempt + 1);
                    continue;  // Try another image
                }

                r = _fingerprint.fingerFastSearch();
                if (r == FINGERPRINT_OK) {
                    matches[attempt].id = _fingerprint.fingerID;
                    matches[attempt].confidence = _fingerprint.confidence;
                    matches[attempt].valid = (matches[attempt].confidence >= MIN_CONFIDENCE_THRESHOLD);

                    Serial.printf("[JM101] Read %d: ID=%u, confidence=%u, valid=%s\n",
                                  attempt + 1, matches[attempt].id, matches[attempt].confidence,
                                  matches[attempt].valid ? "YES" : "NO");

                    if (matches[attempt].valid) {
                        successful_matches++;
                    }
                    read_successful = true;
                    break;
                }
                if (r == FINGERPRINT_NOTFOUND) {
                    matches[attempt].valid = false;
                    Serial.printf("[JM101] Read %d: No match found\n", attempt + 1);
                    read_successful = true;
                    break;
                }
                Serial.printf("[JM101] fingerFastSearch error=0x%02X on read %d\n", r, attempt + 1);
            } else if (p == FINGERPRINT_NOFINGER) {
                continue;
            } else if (p == FINGERPRINT_IMAGEFAIL || p == FINGERPRINT_IMAGEMESS ||
                      p == FINGERPRINT_FEATUREFAIL || p == FINGERPRINT_INVALIDIMAGE) {
                continue;  // Bad image, try again
            } else {
                Serial.printf("[JM101] getImage error=0x%02X on read %d\n", p, attempt + 1);
                return HL_ERR_SENSOR;
            }
        }

        if (!read_successful) {
            Serial.printf("[JM101] Failed to complete verification read %d\n", attempt + 1);
        }

        // Brief pause between reads (except last one)
        if (attempt < NUM_VERIFICATION_READS - 1) {
            delay(200);
        }
    }

    // Analyze results: Need majority of successful matches with same ID
    if (successful_matches == 0) {
        Serial.println("[JM101] No successful matches in verification reads");
        return HL_ERR_NO_MATCH;
    }

    // Find the most common valid ID and calculate average confidence
    uint16_t best_id = 0;
    int id_count = 0;
    int total_confidence = 0;
    int confidence_readings = 0;

    // Count occurrences of each valid ID
    for (int i = 0; i < NUM_VERIFICATION_READS; i++) {
        if (!matches[i].valid) continue;

        int current_count = 0;
        int current_confidence_sum = 0;
        int current_confidence_count = 0;

        for (int j = 0; j < NUM_VERIFICATION_READS; j++) {
            if (matches[j].valid && matches[j].id == matches[i].id) {
                current_count++;
                current_confidence_sum += matches[j].confidence;
                current_confidence_count++;
            }
        }

        // Update best match if this ID has more occurrences
        if (current_count > id_count) {
            best_id = matches[i].id;
            id_count = current_count;
            total_confidence = current_confidence_sum;
            confidence_readings = current_confidence_count;
        }
    }

    // Require majority agreement (at least 2 out of 3 reads)
    const int MIN_AGREEMENT = (NUM_VERIFICATION_READS + 1) / 2;
    if (id_count < MIN_AGREEMENT) {
        Serial.printf("[JM101] Insufficient agreement: %d/%d reads matched same ID\n",
                      id_count, NUM_VERIFICATION_READS);
        return HL_ERR_NO_MATCH;
    }

    matched_id = best_id;
    score = total_confidence / confidence_readings;  // Average confidence

    Serial.printf("[JM101] Authentication successful: ID=%u, avg_confidence=%u (%d/%d reads agreed)\n",
                  matched_id, score, id_count, NUM_VERIFICATION_READS);

    return HL_OK;
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
    Serial.printf("[JM101] Enrolling fingerprint to slot %u with multiple reads...\n", slot_id);

    // Configuration for multiple reads
    const int NUM_ENROLLMENT_READS = 5;  // Capture 5 times for maximum accuracy
    const int MIN_WAIT_BETWEEN_READS_MS = 800;  // Wait time for finger repositioning

    // Strategy for 5 reads:
    // Read1->Buffer1, Read2->Buffer2, CreateModel, Store to temp_slot1
    // Read3->Buffer1, Read4->Buffer2, CreateModel, Store to temp_slot2
    // Read5->Buffer1, Load temp_slot1 to Buffer2, Merge, Store to temp_slot1
    // Load temp_slot2 to Buffer2, Load temp_slot1 to Buffer1, Final merge

    uint16_t temp_slot1 = 200;  // Temporary storage slots
    uint16_t temp_slot2 = 201;

    for (int read_num = 1; read_num <= NUM_ENROLLMENT_READS; read_num++) {
        Serial.printf("[JM101] 第%d/%d次录入：请将手指放在传感器上...\n", read_num, NUM_ENROLLMENT_READS);

        uint32_t deadline = millis() + timeout_ms;

        // Wait for finger placement
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

        // Convert image to template in appropriate buffer
        uint8_t buffer_id = ((read_num % 2) == 1) ? 1 : 2;  // Alternate buffers

        if (_fingerprint.image2Tz(buffer_id) != FINGERPRINT_OK) {
            Serial.printf("[JM101] Character generation failed on capture %d\n", read_num);
            return HL_ERR_SENSOR;
        }

        // Handle template creation and merging for 5 reads
        if (read_num == 2) {
            // After first two reads: create first template
            if (_fingerprint.createModel() != FINGERPRINT_OK) {
                Serial.println("[JM101] Template creation failed after first two captures");
                return HL_ERR_SENSOR;
            }
            if (_fingerprint.storeModel(temp_slot1) != FINGERPRINT_OK) {
                Serial.println("[JM101] Temporary template storage failed");
                return HL_ERR_SENSOR;
            }
            Serial.println("[JM101] 基础模板已创建 (前2次录入)");

        } else if (read_num == 4) {
            // After reads 3 and 4: create second template
            if (_fingerprint.createModel() != FINGERPRINT_OK) {
                Serial.println("[JM101] Template creation failed after captures 3-4");
                return HL_ERR_SENSOR;
            }
            if (_fingerprint.storeModel(temp_slot2) != FINGERPRINT_OK) {
                Serial.println("[JM101] Second template storage failed");
                return HL_ERR_SENSOR;
            }
            Serial.println("[JM101] 第二模板已创建 (第3-4次录入)");

        } else if (read_num == 5) {
            // Fifth read: merge with first template
            if (_fingerprint.loadModel(temp_slot1) != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to load first template");
                return HL_ERR_SENSOR;
            }
            // Read 5 is in buffer 1, first template loaded to buffer 2
            if (_fingerprint.createModel() != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to merge read 5 with first template");
                return HL_ERR_SENSOR;
            }
            if (_fingerprint.storeModel(temp_slot1) != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to store merged template");
                return HL_ERR_SENSOR;
            }
            Serial.println("[JM101] 第5次录入已合并");

            // Now final merge: load both templates and create final result
            if (_fingerprint.loadModel(temp_slot1) != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to load merged template 1");
                return HL_ERR_SENSOR;
            }
            // Template 1 is now in buffer 1, load template 2 to buffer 2
            if (_fingerprint.loadModel(temp_slot2) != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to load template 2");
                return HL_ERR_SENSOR;
            }
            // Final merge of all 5 captures
            if (_fingerprint.createModel() != FINGERPRINT_OK) {
                Serial.println("[JM101] Failed to create final merged template");
                return HL_ERR_SENSOR;
            }
            Serial.println("[JM101] 最终模板合并完成 (5次录入综合)");
        }

        // Ask user to remove finger between captures (except after last one)
        if (read_num < NUM_ENROLLMENT_READS) {
            Serial.printf("[JM101] 请移开手指，准备第%d次录入...\n", read_num + 1);

            // Wait for finger removal
            uint32_t remove_deadline = millis() + 8000;  // 8 seconds to remove finger
            bool finger_removed = false;
            while (millis() < remove_deadline) {
                if (_fingerprint.getImage() == FINGERPRINT_NOFINGER) {
                    finger_removed = true;
                    break;
                }
                delay(100);
            }

            if (!finger_removed) {
                Serial.println("[JM101] 警告：未检测到手指移开，继续下一次录入");
            }

            delay(MIN_WAIT_BETWEEN_READS_MS);  // Brief pause between reads
        }
    }

    // Store the final merged template in the requested slot
    if (_fingerprint.storeModel(slot_id) != FINGERPRINT_OK) {
        Serial.println("[JM101] Final template storage failed");
        return HL_ERR_SENSOR;
    }

    // Clean up temporary slots
    _fingerprint.deleteModel(temp_slot1);
    _fingerprint.deleteModel(temp_slot2);

    Serial.printf("[JM101] 指纹录入成功！槽位 %u，共录入 %d 次\n",
                  slot_id, NUM_ENROLLMENT_READS);
    Serial.println("[JM101] 5次录入模板已合并，获得最高精度");
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
