# SDK ↔ 硬件固件 契约

**版本：** HumanLink Protocol v0.3  
**状态：** 规范性文档（唯一权威来源）  
**适用方：** PC SDK（构造 + 验证两侧）、固件（signedHash 构造）、Agent 平台（actionHash 构造）

本文档是Hash 构造规范, actionHash 与 signedHash 的唯一规范。固件实现与 PC SDK 实现必须严格遵守本文档，禁止各自独立诠释。

---

## 1. actionHash

### 1.1 定义

`actionHash` 将一次授权绑定到**具体操作参数 + 目标设备 + 一次性随机数**，防止签名被挪用到其他操作或其他设备。

### 1.2 构造公式

```
actionHash = SHA-256(action ‖ SP ‖ param_1 ‖ SP ‖ param_2 ‖ ... ‖ SP ‖ nonce ‖ SP ‖ requiredIssuerDID)
```

其中：
- `‖` 表示字节级拼接
- `SP` = `0x1F`（ASCII Unit Separator），作为字段分隔符，防止拼接歧义
- 所有字段编码为 **UTF-8 字节串**
- `params` 按**字典序（lexicographic key order）**排列，仅包含操作的显著参数（排除 session token 等易变字段）
- `nonce` = 同一 Challenge 中的 `challenge.nonce`（16 位 hex 字符串的 UTF-8 编码）
- `requiredIssuerDID` = 完整 DID 字符串（如 `did:key:z6MkBob...`）

### 1.3 示例

操作：向 Alice 转账 $500 USD

| 字段 | 值 |
|------|-----|
| action | `transfer` |
| params（按字典序） | `amount=500`, `currency=USD`, `recipient=Alice` |
| nonce | `a1f3b7c2d4e56789` |
| requiredIssuerDID | `did:key:z6MkBob...` |

拼接字节（伪代码）：
```python
SP = b'\x1f'
raw = (
    b'transfer' + SP +
    b'amount=500' + SP +
    b'currency=USD' + SP +
    b'recipient=Alice' + SP +
    b'a1f3b7c2d4e56789' + SP +
    b'did:key:z6MkBob...'
)
actionHash = hashlib.sha256(raw).hexdigest()
```

### 1.4 安全性质

- 相同操作 + 不同 nonce → 不同 actionHash（防截获重放）
- 相同操作 + 不同 requiredIssuerDID → 不同 actionHash（防设备替换攻击）
- 参数字典序固定 → 防因排列不同导致 SDK 侧与平台侧计算结果不一致

### 1.5 谁构造 actionHash

| 场景 | 构造方 |
|------|--------|
| 云端流程 | Agent 平台（拦截真实 API 参数后构造） |
| 本地流程 (OpenClaw) | `HumanLinkVerifier.create_challenge()` |

> 固件**不**构造 actionHash，只接收并将其包含在 `h_doc` 中签名。

---

## 2. h_doc（Challenge 哈希）

### 2.1 定义

`h_doc` 是 Challenge 骨架的哈希摘要，作为固件签名的间接输入，使固件签名绑定到完整 Challenge 内容。

### 2.2 构造公式

```
h_doc = SHA-256(assertion_skeleton_canonical)
```

其中 `assertion_skeleton_canonical` 是 Assertion 中**除 `proof` 字段之外**的全部内容，经过以下规范化：
1. JSON 字段按键名字典序排序（递归）
2. 无多余空格和换行（compact JSON）
3. UTF-8 编码

**包含字段：** `@context`, `type`, `id`, `version`, `created`, `device`, `subject`, `challenge`, `evidence`  
**排除字段：** `proof`（签名字段本身）

> 这等效于 JSON-LD Canonicalization（RDFC-1.0）的简化版本。v0.4 将采用完整 RDFC-1.0。

### 2.3 示例（伪代码）

```python
import json, hashlib

skeleton = {
    "@context": "https://humanlink.dev/protocol/v0-3",
    "type": "HumanPresenceAssertion",
    "id": "urn:uuid:...",
    "version": "0.3",
    "created": "2025-06-14T10:23:00Z",
    "device": { ... },
    "subject": { ... },
    "challenge": { ... },
    "evidence": { ... }
    # "proof" 字段不包含
}

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

h_doc = hashlib.sha256(canonical(skeleton).encode('utf-8')).digest()  # 32 bytes
```

PC SDK 在组装完 `device`、`subject`、`challenge`、`evidence` 后，**先计算 h_doc**，再通过 USB Serial 发给固件要求签名。

---

## 3. signedHash（固件签名输入）

### 3.1 定义

`signedHash` 是固件内部由 ATECC608A 实际签名的 32 字节哈希。它将指纹匹配证据、传感器身份、防重放令牌和 Challenge 哈希绑定为单一签名输入。

### 3.2 构造公式

```
signedHash = SHA-256(
    matched_id[2B, big-endian] ‖
    score[2B, big-endian]      ‖
    sensor_serial[32B]         ‖
    nonce[8B]                  ‖
    h_doc[32B]
)
```

总输入：**76 字节** → SHA-256 → 32 字节 signedHash

### 3.3 字段来源

| 字段 | 来源 | 字节数 | 说明 |
|------|------|--------|------|
| `matched_id` | JM-101 AutoIdentify 响应 | 2 | 匹配的指纹槽位号，大端序 |
| `score` | JM-101 AutoIdentify 响应 | 2 | 匹配置信度，大端序 |
| `sensor_serial` | JM-101 GetChipSN（0x34）响应 | 32 | 传感器芯片唯一序列号 |
| `nonce` | PC SDK 生成，通过 USB Serial 下发 | 8 | 防重放绑定（raw bytes，从 hex 解码） |
| `h_doc` | PC SDK 计算后通过 USB Serial 下发 | 32 | Challenge + Assertion 骨架哈希 |

### 3.4 固件实现（C++）

```cpp
// firmware/src/main.cpp: runAuth()
uint8_t payload_buf[2 + 2 + 32 + 8 + 32];  // = 76 bytes
payload_buf[0] = (uint8_t)(matched_id >> 8);
payload_buf[1] = (uint8_t)(matched_id & 0xFF);
payload_buf[2] = (uint8_t)(score >> 8);
payload_buf[3] = (uint8_t)(score & 0xFF);
memcpy(payload_buf + 4,      sensor_sn, 32);
memcpy(payload_buf + 36,     nonce,     8);
memcpy(payload_buf + 44,     h_doc,     32);

uint8_t signed_hash[32];
sha256(payload_buf, 76, signed_hash);
// → ATECC608A.sign(signed_hash)
```

### 3.5 PC SDK 验证（Python）

```python
import struct, hashlib

def rebuild_signed_hash(matched_id: int, score: int,
                         sensor_serial: bytes, nonce: bytes, h_doc: bytes) -> bytes:
    assert len(sensor_serial) == 32
    assert len(nonce) == 8
    assert len(h_doc) == 32

    raw = (
        struct.pack('>HH', matched_id, score) +  # 4 bytes, big-endian
        sensor_serial +                           # 32 bytes
        nonce +                                   # 8 bytes
        h_doc                                     # 32 bytes
    )                                             # total: 76 bytes
    return hashlib.sha256(raw).digest()

# 验证 ECDSA 签名
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

def verify_assertion_signature(pubkey_bytes: bytes,
                                signed_hash: bytes,
                                signature_rs: bytes) -> bool:
    """
    pubkey_bytes: 64-byte uncompressed P-256 public key (x‖y, without 0x04 prefix)
    signed_hash:  32-byte SHA-256 digest (已重建)
    signature_rs: 64-byte raw signature (r‖s)
    """
    # 将 64 字节 raw 格式转换为 DER 格式
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
    r = int.from_bytes(signature_rs[:32], 'big')
    s = int.from_bytes(signature_rs[32:], 'big')
    sig_der = encode_dss_signature(r, s)

    # 重建公钥
    x = int.from_bytes(pubkey_bytes[:32], 'big')
    y = int.from_bytes(pubkey_bytes[32:], 'big')
    pub = ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()

    # 验证（Prehashed）
    pub.verify(sig_der, signed_hash, ec.ECDSA(hashes.Prehashed()))
    return True  # 不抛出则通过
```

---

## 4. 端到端哈希链路

```
操作参数                        PC SDK                           固件
────────                        ────────                         ────

action + params + nonce         ①  actionHash = SHA-256(...)
+ requiredIssuerDID             →  写入 challenge.actionHash

assertion 骨架（除proof）        ②  h_doc = SHA-256(canonical(skeleton))
                                →  通过 USB Serial 发送 h_doc + nonce

                                                                 ③  signedHash =
                                                                    SHA-256(matched_id
                                                                    ‖ score
                                                                    ‖ sensor_serial
                                                                    ‖ nonce       ← 绑定防重放
                                                                    ‖ h_doc)      ← 绑定操作

                                                                 ④  sig = ATECC608A.sign(signedHash)
                                                                    → 返回 sig, pubkey, matched_id,
                                                                      score, sensor_serial, nonce

                                ⑤  PC SDK 回填 proof:
                                   proof.signedHash = signedHash (hex)
                                   proof.signature  = sig (base64)

Verifier                        ⑥  重建 signedHash，验证签名
```

---

## 5. 互操作性要求

任何实现 HumanLink HAI（Hardware Abstraction Interface）的设备，其 signedHash 构造**必须**与第 3 节完全一致，以确保 HumanLinkVerifier 可无缝验证不同硬件的签名。

字段顺序、字节序、长度均为**规范性要求（MUST）**，不得变更。
