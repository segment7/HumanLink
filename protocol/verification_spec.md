# 验证规范

>**（10 步校验流程）**

**版本：** HumanLink Protocol v0.3  
**状态：** 规范性文档  
**适用方：** HumanLinkVerifier（本地/云端统一，chain_check 配置决定步骤 10 是否执行）

---

## 1. 概述

Verifier 接收 `HumanPresenceAssertion` 后，**必须**按顺序执行以下 10 步校验。任何一步失败则拒绝断言，记录失败步骤和原因，不执行后续步骤。

| 步骤 | 类别 | 是否需要联网 |
|------|------|:---:|
| 1 | 结构校验 | ❌ |
| 2 | 设备绑定 | ❌ |
| 3 | actionHash 校验 | ❌ |
| 4 | origin 绑定 | ❌ |
| 5 | nonce 防重放 | ❌ |
| 6 | 时间窗口 | ❌ |
| 7 | matchScore 阈值 | ❌ |
| 8 | Attestation 信任策略 | ❌ |
| 9 | ECDSA 签名验证 | ❌ |
| 10 | 链上状态校验 | ✅（可降级） |

---

## 2. 步骤详述

### 步骤 1：结构校验

校验 Assertion 包含所有必须字段，格式符合 [assertion_spec.md](./assertion_spec.md) §2。

```python
REQUIRED_FIELDS = [
    "@context", "type", "id", "version", "created",
    "device.id", "device.attestation",
    "subject.localId", "subject.isRegistered",
    "challenge.origin", "challenge.action", "challenge.requiredIssuerDID",
    "challenge.actionHash", "challenge.nonce", "challenge.issuedAt",
    "evidence.matchScore", "evidence.sensorSerial",
    "proof.type", "proof.signedHash", "proof.signature", "proof.verificationMethod"
]

assert assertion["@context"] == "https://humanlink.dev/protocol/v0-3"
assert assertion["type"] == "HumanPresenceAssertion"
assert assertion["version"] == "0.3"
assert assertion["proof"]["type"] == "ECDSA-P256"
```

**失败原因：** `INVALID_STRUCTURE`

---

### 步骤 2：设备绑定

```python
assert assertion["device"]["id"] == challenge["requiredIssuerDID"]
assert assertion["proof"]["verificationMethod"] == challenge["requiredIssuerDID"] + "#key-0"
```

> 防止攻击者用其他合法设备替换签发设备。`requiredIssuerDID` 在 Challenge 中由请求方写定，固件在接受签名前亦需自验（见 HAI 规范 §5.2）。

**失败原因：** `DEVICE_BINDING_MISMATCH`

---

### 步骤 3：actionHash 校验

按 [hash_construction.md](./hash_construction.md) §1 规范重建 actionHash，与 Assertion 中的值对比。

```python
expected = build_action_hash(
    action=challenge["action"],
    params=challenge["params"],          # 按字典序
    nonce=challenge["nonce"],
    required_issuer_did=challenge["requiredIssuerDID"]
)
assert assertion["challenge"]["actionHash"] == expected
```

**失败原因：** `ACTION_HASH_MISMATCH`

---

### 步骤 4：origin 绑定

```python
assert assertion["challenge"]["origin"] == expected_origin
# expected_origin 由 Verifier 从 Challenge 请求上下文获取，不来自 Assertion 本身
```

- 云端流程：`expected_origin` = 平台域名（如 `"copilot.example.com"`）
- 本地流程：`expected_origin` = `"local://openclaw"` 或配置中指定的本地来源标识

**失败原因：** `ORIGIN_MISMATCH`

---

### 步骤 5：nonce 防重放

```python
assert challenge["nonce"] not in used_nonces_db.get(device_did)
used_nonces_db.add(device_did, challenge["nonce"], ttl=max_age_seconds * 2)
```

- nonce 与 `device_did` 联合唯一
- 存储窗口建议 ≥ 2 × `max_age_seconds`（默认 60 秒）
- 本地流程可用内存 set 代替 DB

**失败原因：** `NONCE_REPLAY`

---

### 步骤 6：时间窗口

```python
from datetime import datetime, timezone, timedelta

created = datetime.fromisoformat(assertion["created"])
now = datetime.now(timezone.utc)
age_seconds = (now - created).total_seconds()

assert 0 <= age_seconds <= config["max_age_seconds"]  # 默认 30s
```

**失败原因：** `EXPIRED`（age > max_age）或 `FUTURE_TIMESTAMP`（age < 0）

---

### 步骤 7：matchScore 阈值

```python
assert assertion["evidence"]["matchScore"] >= config["min_match_score"]  # 默认 100
```

**失败原因：** `SCORE_TOO_LOW`

---

### 步骤 8：Attestation 信任策略

根据 `config.trust_policy` 评估 `device.attestation`：

```python
att = assertion["device"]["attestation"]

if config["trust_policy"] == "default":
    assert att["secureElement"] in ACCEPTED_SECURE_ELEMENTS  # ["ATECC608A"]
    assert att["sensorFAR"] <= config["max_sensor_far"]      # 默认 0.001 (0.1%)
    # livenessDetection 不强制（v0.3 参考硬件无此能力）

elif config["trust_policy"] == "strict":
    assert att["livenessDetection"] == True
    assert att["secureElement"] in ACCEPTED_SECURE_ELEMENTS
    assert att["sensorFAR"] <= 0.0001

elif config["trust_policy"] == "permissive":
    assert att["secureElement"] is not None  # 至少有 SE
```

**失败原因：** `ATTESTATION_POLICY_FAILED`

---

### 步骤 9：ECDSA 签名验证

按 [hash_construction.md](./hash_construction.md) §3 重建 `signedHash`，用设备公钥验证签名。

```python
# 1. 重建 signedHash
sensor_serial = bytes.fromhex(assertion["evidence"]["sensorSerial"])
nonce_bytes   = bytes.fromhex(assertion["challenge"]["nonce"])
h_doc_bytes   = compute_h_doc(assertion)  # 见 hash_construction.md §2

expected_signed_hash = rebuild_signed_hash(
    matched_id=int(assertion["subject"]["localId"].replace("slot-", "")),
    score=assertion["evidence"]["matchScore"],
    sensor_serial=sensor_serial,
    nonce=nonce_bytes,
    h_doc=h_doc_bytes
)

# 2. 核验 Assertion 中的 signedHash 与重建值一致
assert bytes.fromhex(assertion["proof"]["signedHash"]) == expected_signed_hash

# 3. 解析公钥（从 verificationMethod 对应的 did:key 解码）
pubkey_bytes = decode_did_key(assertion["proof"]["verificationMethod"])

# 4. 验签
verify_assertion_signature(
    pubkey_bytes=pubkey_bytes,
    signed_hash=expected_signed_hash,
    signature_rs=base64.b64decode(assertion["proof"]["signature"])
)
```

**失败原因：** `SIGNED_HASH_MISMATCH`（重建值不一致）或 `SIGNATURE_INVALID`（验签失败）

---

### 步骤 10：链上状态校验（可选）

根据 `config.chain_check` 决定是否执行：

```python
if config["chain_check"] == "required":
    # 强制联网校验
    _chain_verify(assertion)

elif config["chain_check"] == "optional":
    # 有网则查，无网降级
    try:
        _chain_verify(assertion)
    except NetworkUnavailable:
        result.chain_checked = False
        result.chain_check_reason = "skipped_offline"

elif config["chain_check"] == "skip":
    result.chain_checked = False
    result.chain_check_reason = "skipped_config"
```

`_chain_verify()` 执行：

```python
def _chain_verify(assertion):
    device_did = assertion["device"]["id"]
    assertion_id = assertion["id"]

    # 检查设备是否已注册为合法 Issuer
    assert issuer_registry.isValidIssuer(device_did), "DEVICE_NOT_REGISTERED"

    # 检查断言是否已被撤销
    assert not assertion_status_registry.isRevoked(assertion_id), "ASSERTION_REVOKED"
```

**失败原因（需联网）：** `DEVICE_NOT_REGISTERED` 或 `ASSERTION_REVOKED`

---

## 3. 验证结果结构

```python
@dataclass
class VerificationResult:
    valid: bool
    failure_step: Optional[int]        # 1-10，失败时非 None
    failure_reason: Optional[str]      # 上述失败原因常量
    device_did: str
    assertion_id: str
    chain_checked: bool
    chain_check_reason: Optional[str]  # "ok" / "skipped_offline" / "skipped_config"
    verified_at: datetime
```

---

## 4. 配置参数

```yaml
# Verifier SDK 统一配置（本地和云端均使用相同配置结构）

verification:
  chain_check: "optional"     # required | optional | skip
  max_age_seconds: 30
  min_match_score: 100
  max_sensor_far: 0.001       # 0.1%
  trust_policy: "default"     # default | strict | permissive
  enforce_device_binding: true
```

---

## 5. 审计日志

每次验证（无论通过与否）写入审计记录：

```json
{
  "audit_version": "1.0",
  "record_id": "urn:uuid:...",
  "timestamp": "2025-06-14T10:23:00Z",
  "assertion_id": "urn:uuid:550e8400...",
  "device_did": "did:key:z6MkUser...",
  "match_score": 188,
  "valid": true,
  "failure_step": null,
  "failure_reason": null,
  "chain_checked": false,
  "chain_check_reason": "skipped_offline"
}
```
