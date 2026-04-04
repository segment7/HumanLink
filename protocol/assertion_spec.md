# HumanPresenceAssertion 格式规范

>**在场断言数据规范**

**版本：** HumanLink Protocol v0.3  
**状态：** 规范性文档  
**适用方：** PC SDK、Verifier SDK、Agent 平台、审计系统

---

## 1. 概述

`HumanPresenceAssertion` 是 HumanLink 协议的核心数据结构，表示：

> 在特定时刻，有持有已注册设备的真实人类物理在场并确认了某操作。

一次按压产生一个 Assertion，不可缓存、不可复用。

---

## 2. 完整结构

```json
{
  "@context": "https://humanlink.dev/protocol/v0-3",
  "type": "HumanPresenceAssertion",
  "id": "urn:uuid:550e8400-e29b-41d4-a716-446655440000",
  "version": "0.3",
  "created": "2025-06-14T10:23:00Z",

  "device": {
    "id": "did:key:z6MkBob...",
    "attestation": {
      "sensorType": "optical_fingerprint",
      "sensorFAR": 0.00001,
      "sensorFRR": 0.01,
      "secureElement": "ATECC608A",
      "livenessDetection": false
    }
  },

  "subject": {
    "localId": "slot-03",
    "isRegistered": true
  },

  "challenge": {
    "origin": "copilot.example.com",
    "action": "transfer",
    "requiredIssuerDID": "did:key:z6MkBob...",
    "actionHash": "sha256(action ‖ param1 ‖ param2 ‖ ... ‖ nonce ‖ requiredIssuerDID)",
    "nonce": "a1f3b7c2d4e56789",
    "issuedAt": "2025-06-14T10:22:58Z",
    "display": {
      "title": "转账确认",
      "summary": "向 Alice 转账 $500.00",
      "risk": "high",
      "source": "copilot.example.com"
    }
  },

  "evidence": {
    "matchScore": 188,
    "sensorSerial": "A3B4C5D6E7F8..."
  },

  "proof": {
    "type": "ECDSA-P256",
    "signedHash": "<hex64>",
    "signature": "<der or r||s base64>",
    "verificationMethod": "did:key:z6MkBob...#key-0"
  }
}
```

---

## 3. 字段规范

### 3.1 顶层字段

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `@context` | string | ✅ | 固定值 `"https://humanlink.dev/protocol/v0-3"` |
| `type` | string | ✅ | 固定值 `"HumanPresenceAssertion"` |
| `id` | string | ✅ | URN UUID v4，全局唯一，用于引用和撤销查询 |
| `version` | string | ✅ | 固定值 `"0.3"` |
| `created` | string | ✅ | ISO 8601 UTC 时间戳，Verifier 校验时间窗口（≤30s） |

### 3.2 `device` 对象

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `device.id` | string | ✅ | 设备 DID，格式 `did:key:z6Mk...`，由 ATECC608A P-256 公钥派生 |
| `device.attestation.sensorType` | string | ✅ | 传感器类型，当前支持：`optical_fingerprint` |
| `device.attestation.sensorFAR` | float | ✅ | 误识率（False Accept Rate），JM-101 为 0.00001 |
| `device.attestation.sensorFRR` | float | ✅ | 拒识率（False Reject Rate），JM-101 为 0.01 |
| `device.attestation.secureElement` | string | ✅ | 安全芯片型号，当前支持：`ATECC608A` |
| `device.attestation.livenessDetection` | bool | ✅ | 是否具备活体检测能力，JM-101 为 `false` |

**信任分级（Verifier 决策参考）：**

| 组合 | 信任等级 |
|------|------|
| ATECC608A + livenessDetection=true | 最高 |
| ATECC608A + livenessDetection=false | 标准（当前参考实现） |
| 无安全芯片 | 不接受（v0.3 最低要求有 SE） |

### 3.3 `subject` 对象

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `subject.localId` | string | ✅ | 传感器内部槽位标识（如 `"slot-03"`），对应 JM-101 的 `matched_id` |
| `subject.isRegistered` | bool | ✅ | 该槽位是否有已注册模板，Verifier 在未注册时拒绝 |

> 协议层不涉及真实身份。`slot-03 = 张三` 由应用层维护，不写入 Assertion。

### 3.4 `challenge` 对象

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `challenge.origin` | string | ✅ | 请求来源域名或本地标识（如 `"local://openclaw"`） |
| `challenge.action` | string | ✅ | 操作类型字符串（如 `"transfer"`、`"bash_exec"`） |
| `challenge.requiredIssuerDID` | string | ✅ | 必须由哪台设备签名，设备必须在响应前校验与自身 DID 一致 |
| `challenge.actionHash` | string | ✅ | 操作参数绑定哈希，构造规范见 [hash_construction.md](./hash_construction.md) |
| `challenge.nonce` | string | ✅ | 16 位十六进制（8 字节），一次性随机数，由 SDK 生成 |
| `challenge.issuedAt` | string | ✅ | Challenge 生成时间，ISO 8601 UTC |
| `challenge.display.title` | string | ✅ | 显示给用户的操作标题（≤64 字符） |
| `challenge.display.summary` | string | ✅ | 操作参数摘要（≤256 字符） |
| `challenge.display.risk` | string | ✅ | 风险等级：`"high"` / `"medium"` / `"low"` |
| `challenge.display.source` | string | ✅ | 来源域名，与 `origin` 保持一致 |

### 3.5 `evidence` 对象

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `evidence.matchScore` | int | ✅ | 指纹匹配置信度，Verifier 要求 ≥ `min_match_score`（默认 100） |
| `evidence.sensorSerial` | string | ✅ | 传感器芯片唯一序列号（hex，32 字节），与 `signedHash` 绑定 |

### 3.6 `proof` 对象

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `proof.type` | string | ✅ | 固定值 `"ECDSA-P256"` |
| `proof.signedHash` | string | ✅ | 签名输入哈希（hex64），构造规范见 [hash_construction.md](./hash_construction.md) |
| `proof.signature` | string | ✅ | ECDSA-P256 签名，raw format r‖s（64 字节），base64 编码 |
| `proof.verificationMethod` | string | ✅ | 必须为 `{challenge.requiredIssuerDID}#key-0` |

---

## 4. 约束

1. `proof.verificationMethod` 的 DID 部分 **必须** 与 `challenge.requiredIssuerDID` 完全一致
2. `device.id` **必须** 与 `challenge.requiredIssuerDID` 完全一致
3. `created` 时间距 Verifier 接收时间 **必须** ≤ 30 秒
4. `challenge.nonce` **不得** 在同一设备的任何历史 Assertion 中重复出现
5. `evidence.sensorSerial` **必须** 出现在 `proof.signedHash` 的签名输入中
6. `challenge.nonce` **必须** 出现在 `proof.signedHash` 的签名输入中（防重放绑定）

---

## 5. 生命周期

```
生成                        传输                验证                存档
────                        ────                ────                ────
PC SDK 组装              → Verifier            → 10 步校验        → 本地 DB / 链
(设备签名后)               接收 assertion        (见 verification_spec)  + 可选撤销
```

Assertion 一旦验证通过，PC SDK 将 `id` 写入本地 DB/审计日志，并可选择将撤销状态提交到链上 `AssertionStatusRegistry`。

---

## 6. 版本历史

| 版本 | 变更 |
|------|------|
| v0.3 | 增加 `challenge.nonce` 写入 `signedHash`（防重放绑定加固）；增加 `UserDeviceRegistry` 链上合约 |
| v0.2 | 初始 `signedHash` 结构 |
