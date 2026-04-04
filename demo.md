---
name: HumanLink 项目概述
description: HumanLink 项目的定位、技术栈、协议设计和文件结构
type: project
---

## 项目定位
HumanLink 是 AI Agent 时代的人类授权基础设施。类比 MCP 定义 Agent 如何调用工具，HumanLink 定义 Agent 执行高风险操作前如何留下**不可伪造的人类授权记录**（密码学断言）。

核心原则：**一次按压 = 一份断言 = 一次授权，不缓存，不复用。**

协议版本：HumanLink Protocol v0.3

---

## 硬件技术栈（参考实现 ESP32 U盾）

| 组件 | 型号 | 角色 |
|------|------|------|
| 微控制器 | ESP32-WROOM-32 | 安全飞地控制器，USB Serial 接 PC |
| 指纹传感器 | JM-101 (FPM383C 兼容) | 光学指纹采集与本地模板匹配，UART 57600bps 接 ESP32 |
| 安全芯片 | Microchip ATECC608A | ECDSA P-256 签名，私钥不可读出，I2C 接 ESP32 |
| USB-Serial 芯片 | CH340 / CP2102 | U盾与 PC 物理通信桥梁 |

接线：ESP32 TX0/RX0 ↔ JM-101 UART；ESP32 GPIO21/22 (SDA/SCL) ↔ ATECC608A I2C

---

## 软件技术栈

| 层 | 技术 |
|----|------|
| ESP32 固件 | PlatformIO + Arduino Framework, C++ |
| PC SDK 守护进程 | Python 3.11+, FastAPI, uvicorn |
| 链上合约 | Solidity 0.8.x, Hardhat, Sepolia 测试网 |
| Verifier SDK | Python 3.11+ |

PC SDK 第三方库：`fastapi` + `uvicorn`、`pyserial`（USB Serial）、`ecdsa`（签名验证）、`pyld`（JSON-LD 规范化）、`web3.py`（链上交互）、`sqlite3`（本地存储）、`websockets`（云端流程 WebSocket）

---

## 核心数据结构：HumanPresenceAssertion

```json
{
  "@context": "https://humanlink.dev/protocol/v0-3",
  "type": "HumanPresenceAssertion",
  "device": { "id": "did:key:z6Mk...", "attestation": {...} },
  "subject": { "localId": "slot-03", "isRegistered": true },
  "challenge": {
    "origin": "copilot.example.com",
    "action": "transfer",
    "requiredIssuerDID": "did:key:z6Mk...",
    "actionHash": "sha256(action ‖ params ‖ nonce ‖ requiredIssuerDID)",
    "nonce": "...",
    "display": { "title": "...", "summary": "...", "risk": "high" }
  },
  "evidence": { "matchScore": 188, "sensorSerial": "..." },
  "proof": {
    "type": "ECDSA-P256",
    "signedHash": "sha256(matched_id ‖ score ‖ sensor_serial ‖ h_doc)",
    "signature": "...",
    "verificationMethod": "did:key:z6Mk...#key-0"
  }
}
```

---

## 链上合约（Sepolia）

- `IssuerRegistry.sol`：设备注册/注销/查询
- `UserDeviceRegistry.sol`：用户账号 ↔ 设备 DID 绑定（本地流程主用）
- `AssertionStatusRegistry.sol`：断言撤销

**不上链**：生物特征、私钥、Assertion 原文、用户真实身份

---

## 10 步验证流程

1. 结构校验
2. 设备绑定（device.id == requiredIssuerDID）
3. actionHash 校验
4. origin 绑定
5. nonce 防重放
6. 时间窗口（30 秒）
7. matchScore ≥ min_match_score
8. attestation 满足 trust_policy
9. ECDSA 签名验证
10. 链上校验：isValidIssuer() + isRevoked()（本地流程可选）

---

## 本地 vs 云端 对比

| | 云端 平台 | 本地 |
|--|----------|----------|
| Challenge 生成方 | 云端平台服务器 | 本地 OpenClaw |
| 链上检查 | 必须 | 可选（降级为本地信任） |
| 举证对象 | 平台向第三方举证 | 用户向应用/审计方自证 |
| 通信 | WebSocket 接收云端 Challenge | USB Serial 直连 |

本地 集成：OpenClaw（本地 AI Gateway）作为第四层护栏，通过 `approval_hook` 调用 HumanLink 本地 SDK。

---

## 文件结构

```
humanlink/
├── protocol/          # 协议规范
├── sdk/               # Verifier SDK（verifier.py, client.py）
├── contracts/         # 链上合约（IssuerRegistry, UserDeviceRegistry, AssertionStatusRegistry）
├── reference/
│   ├── firmware/      # ESP32 固件 C++（main.cpp, jm101.cpp, atecc608a.cpp）
│   ├── core/          # PC SDK 守护进程 Python（hardware/, assertion/, identity/, crypto/, chain/, api/, db/）
│   └── apps/
│       ├── cloud_platform/  # 云端 Demo（WebSocket 模拟云端）
│       └── local_openclaw/  # 本地 OpenClaw Demo
├── config.yaml
└── requirements.txt
```

PC SDK API 端点（localhost:8765）：
- `POST /auth/challenge`
- `GET /auth/status`
- `GET /device/did`
- `GET /device/attestation`
- `POST /assertion/revoke`

---

**Why:** 项目是黑客松 Demo，需要端到端跑通 HumanLink 协议。
**How to apply:** 开发时以参考实现为准，SDK 在 `sdk/` 和 `reference/core/`，固件在 `reference/firmware/`，合约在 `contracts/`。
