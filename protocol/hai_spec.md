# Hardware Abstraction Interface (HAI) 规范

>**硬件规范**

**版本：** HumanLink Protocol v0.3  
**状态：** 规范性文档  
**适用方：** 固件开发者、硬件厂商、PC SDK 硬件层

---

## 1. 概述

HAI（Hardware Abstraction Interface）定义了 HumanLink 协议对**硬件设备**的最小接口约定。任何满足 HAI 规范的设备均可作为合法的 HumanLink Issuer（签发者），接受 Verifier SDK 验证。

HAI 包含两层：

| 层 | 职责 |
|----|------|
| **传感器层（BioSensor）** | 采集生物特征、执行本地匹配，输出 `matched_id` + `score` + `sensor_serial` |
| **安全元素层（SecureElement）** | ECDSA-P256 签名，私钥永不离芯片，输出 `signature` + `public_key` |

---

## 2. 传感器层接口

### 2.1 方法

#### `enroll(slot: uint16) → EnrollResult`

注册生物特征到指定槽位。

| 参数 | 类型 | 说明 |
|------|------|------|
| `slot` | uint16 | 目标槽位编号（0 ~ capacity-1） |

| 返回字段 | 类型 | 说明 |
|----------|------|------|
| `status` | enum | `OK` / `ALREADY_ENROLLED` / `SENSOR_ERROR` |
| `slot` | uint16 | 实际使用的槽位 |

#### `identify(timeout_ms: uint32) → IdentifyResult`

采集生物特征并在所有已注册模板中搜索。

| 参数 | 类型 | 说明 |
|------|------|------|
| `timeout_ms` | uint32 | 最大等待时间（毫秒），推荐 30000 |

| 返回字段 | 类型 | 说明 |
|----------|------|------|
| `status` | enum | `OK` / `NO_MATCH` / `TIMEOUT` / `NOT_ENROLLED` / `SENSOR_ERROR` |
| `matched_id` | uint16 | 匹配的槽位号（`status=OK` 时有效） |
| `score` | uint16 | 匹配置信度（越高越好，JM-101 范围 0–300，推荐阈值 ≥100） |

#### `get_serial() → bytes[32]`

返回传感器芯片唯一序列号（32 字节）。该值稳定不变，用于 `signedHash` 构造中的传感器绑定。

#### `get_template_count() → int`

返回当前已注册的模板数量。

#### `cancel() → void`

中断正在进行的 `identify()` 或 `enroll()` 操作。

### 2.2 参考实现：JM-101 / FPM383C

| HAI 方法 | JM-101 命令 | 命令码 |
|----------|------------|--------|
| `enroll()` | PS_AutoEnroll | 0x31 |
| `identify()` | PS_AutoIdentify | 0x32 |
| `get_serial()` | GetChipSN | 0x34 |
| `get_template_count()` | PS_ValidTempleteNum | 0x1D |
| `cancel()` | PS_Cancel | 0x30 |

**通信参数：** UART 57600bps 8N2  
**包格式：** `0xEF01` + ADDR(4B) + PID(1B) + LEN(2B) + PAYLOAD + CHECKSUM(2B)

---

## 3. 安全元素层接口

### 3.1 方法

#### `provision() → bool`

首次启动时生成 P-256 密钥对并锁定配置区。

- 若已锁定则跳过，直接返回 `true`
- 锁定后私钥**永不可读取或覆写**
- 锁定状态通过 `is_locked()` 可查询

> **必须锁定才能视为安全设备。** Verifier SDK 的 `trust_policy=default` 要求设备在 Attestation 中声明 `secureElement=ATECC608A`，并要求固件已调用 `provision()` 且已锁定。

#### `is_locked() → bool`

返回配置区是否已锁定。

#### `sign(digest: bytes[32]) → bytes[64]`

对 32 字节摘要执行 ECDSA-P256 签名。

- 签名在芯片内部完成，私钥不输出
- 返回 raw 格式签名（r‖s，各 32 字节，共 64 字节）
- 调用方应预先通过 `nonce()` 命令将摘要加载到 TempKey（ATECC608A 特定流程）

#### `get_public_key() → bytes[64]`

返回设备公钥（P-256 uncompressed，不含 `0x04` 前缀，x‖y 各 32 字节，共 64 字节）。

- 每次调用读取，不重新生成
- 用于 PC SDK 派生 `did:key` DID

### 3.2 参考实现：ATECC608A

| HAI 方法 | ArduinoECCX08 API | 说明 |
|----------|------------------|------|
| `provision()` | `ECCX08.generatePrivateKey(slot, pubkey)` + `ECCX08.lock()` | Slot 0 |
| `is_locked()` | `ECCX08.locked()` | 配置区状态 |
| `sign(digest)` | `ECCX08.nonce(digest)` + `ECCX08.ecSign(0, digest, sig)` | Slot 0 |
| `get_public_key()` | `ECCX08.generatePublicKey(0, pubkey_out)` | 读取，不重新生成 |

**通信参数：** I2C，默认地址 0x60，ESP32 SDA=GPIO21 / SCL=GPIO22

---

## 4. 设备 DID 派生

DID 由公钥确定性派生，首次派生后应持久化（ESP32 NVS）。

```
device_did = "did:key:z" + base58btc(multicodec_prefix + public_key)

其中：
  multicodec_prefix = 0x1200  (P-256 multicodec, 2 bytes)
  public_key        = 64-byte uncompressed P-256 key (x‖y)
  base58btc         = Bitcoin Base58 字母表编码
```

**DID 格式示例：** `did:key:z6MkhaDB8V5K1FtMv82qo8YY...`

---

## 5. USB Serial 通信协议

PC SDK 与设备之间通过 USB Serial（115200bps）交换 newline-delimited JSON。

### 5.1 设备就绪事件（设备 → PC SDK）

设备启动后主动发送：

```json
{
  "event": "ready",
  "protocol": "0.3",
  "device_did": "did:key:z6MkXXX..."
}
```

PC SDK 收到此事件后：
1. 记录 `device_did`
2. 若该 DID 未在链上注册，触发注册流程

### 5.2 auth 命令（PC SDK → 设备）

```json
{
  "cmd": "auth",
  "h_doc": "<hex64>",
  "nonce": "<hex16>",
  "display": {
    "title": "<string, ≤64 chars>",
    "risk": "high|medium|low"
  }
}
```

| 字段 | 说明 |
|------|------|
| `h_doc` | 64 位十六进制（32 字节）Challenge 骨架哈希，见 [hash_construction.md](./hash_construction.md) §2 |
| `nonce` | 16 位十六进制（8 字节），与 `challenge.nonce` 的 raw bytes 一致 |
| `display.title` | 显示给用户（固件打印到串口，未来支持 OLED） |
| `display.risk` | 风险等级，影响未来 UI 展示 |

### 5.3 auth 成功响应（设备 → PC SDK）

```json
{
  "status": "ok",
  "protocol": "0.3",
  "matched_id": 1,
  "score": 188,
  "sensor_serial": "<hex64>",
  "nonce": "<hex16>",
  "signed_hash": "<hex64>",
  "sig": "<base64, 64 bytes r‖s>",
  "pubkey": "<base64, 64 bytes x‖y>"
}
```

PC SDK 使用响应字段：

| 字段 | 用途 |
|------|------|
| `matched_id` + `score` | 填入 `assertion.subject.localId` 和 `assertion.evidence.matchScore` |
| `sensor_serial` | 填入 `assertion.evidence.sensorSerial`，同时用于重建 `signedHash` 验证 |
| `nonce` | **必须与请求 nonce 完全一致**，PC SDK 核验后用于防重放检查 |
| `signed_hash` | 填入 `assertion.proof.signedHash`；PC SDK 应重建并核验一致性 |
| `sig` | 填入 `assertion.proof.signature` |
| `pubkey` | 用于 DID 派生校验（应与已知 `device_did` 一致） |

### 5.4 auth 错误响应

```json
{
  "status": "err",
  "code": 2,
  "msg": "fingerprint no match"
}
```

| 错误码 | 含义 | PC SDK 处理 |
|--------|------|------------|
| 1 | TIMEOUT | 告知用户超时，返回 `False` |
| 2 | NO_MATCH | 指纹不匹配，返回 `False` |
| 3 | SENSOR_ERROR | 硬件故障，记录日志，返回 `False` |
| 4 | SE_ERROR | 安全芯片故障，记录日志，返回 `False` |
| 5 | BAD_INPUT | 命令格式错误，应为 SDK bug，抛出异常 |
| 6 | NOT_ENROLLED | 未注册指纹，提示用户注册 |
| 7 | SIGN_FAIL | 签名失败，记录日志，返回 `False` |

### 5.5 status 命令

```json
{"cmd": "status"}
```

响应：

```json
{
  "status": "ok",
  "state": "idle",
  "provisioned": true,
  "enrolled": 3,
  "protocol": "0.3",
  "device_did": "did:key:z6MkXXX..."
}
```

### 5.6 getDID 命令

```json
{"cmd": "getDID"}
```

响应：

```json
{
  "status": "ok",
  "device_did": "did:key:z6MkXXX...",
  "protocol": "0.3"
}
```

### 5.7 cancel 命令

```json
{"cmd": "cancel"}
```

响应：

```json
{"status": "ok", "msg": "cancelled"}
```

---

## 6. Attestation 格式

设备在 `assertion.device.attestation` 中自报硬件能力，Verifier 据此实施分级信任。

```json
{
  "sensorType": "optical_fingerprint",
  "sensorFAR": 0.00001,
  "sensorFRR": 0.01,
  "secureElement": "ATECC608A",
  "livenessDetection": false
}
```

Attestation 由 PC SDK 从本地配置（`~/.humanlink/config.yaml`）读取并填入 Assertion，不由固件直接生成。

---

## 7. 合规设备最低要求

HAI v0.3 合规设备必须满足：

| 要求 | 说明 |
|------|------|
| 安全元素 | 必须包含支持 ECDSA-P256 的安全芯片，私钥不可读取 |
| 配置锁定 | 安全芯片配置区必须锁定 |
| 传感器 FAR | ≤ 0.001%（JM-101 为 0.001%，满足要求） |
| 唯一序列号 | 传感器必须提供稳定唯一的序列号（32 字节） |
| signedHash 构造 | 必须遵循 [hash_construction.md](./hash_construction.md) §3 规范 |
| nonce 回显 | 响应中必须回显请求的 nonce，供 PC SDK 防重放验证 |
