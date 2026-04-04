# SDK ↔ 本地 AI Gateway 契约

>**SDK ↔ OpenClaw 会话规范**

**版本：** HumanLink Protocol v0.3  
**状态：** 规范性文档  
**适用方：** OpenClaw（approval_hook 实现方）、HumanLink PC SDK（HumanLinkVerifier + HumanLinkClient）

---

## 1. 架构概述

```
Agent 进程
  │ 工具调用
  ▼
OpenClaw（本地 AI Gateway）
  │ 拦截高危操作，触发 approval_hook
  ▼
humanlink_approval(command, context) → bool
  │ 调用
  ▼
HumanLink PC SDK
  ├─ HumanLinkVerifier  ← 生成 Challenge、本地验证
  └─ HumanLinkClient         ← USB Serial 通信
       │
       ▼
     HumanLink 设备（ESP32 + JM-101 + ATECC608A）
       │ 用户按指纹 → 签名
       ▼
     HumanPresenceAssertion
       │
       ▼
     HumanLinkVerifier.verify()
       │ 10 步校验
       ▼
     审计日志写入
       │
       ▼
     return True / False → OpenClaw
```

---

## 2. OpenClaw 侧职责

OpenClaw 作为 approval_hook 的**调用方**，负责：

1. **识别高危操作**：根据 policy 判断是否需要 HumanLink 授权
2. **提供操作上下文**：将工具名、参数、风险等级封装为 `context` dict
3. **调用 approval_hook**：`humanlink_approval(command, context)`
4. **遵从返回值**：`True` = 允许执行，`False` = 拒绝执行
5. **降级策略**：设备未连接时执行 `fallback`（`deny` / `ui` / `allow`）

OpenClaw **不感知** Challenge 内容、Assertion 格式、签名细节。

---

## 3. PC SDK 侧职责

PC SDK 作为 approval_hook 的**实现方**，负责：

1. **构造 Challenge**：生成 `actionHash`、`nonce`、`display`（见 §4.1）
2. **与设备通信**：通过 USB Serial 下发 `auth` 命令，等待签名响应
3. **组装 Assertion**：将设备响应填入 `HumanPresenceAssertion`
4. **本地验证（步骤 1-9）**：见 [verification_spec.md](./verification_spec.md)
5. **可选链上验证（步骤 10）**：有网时查 `IssuerRegistry`
6. **写审计日志**：记录操作 + 断言 ID + 验证结果
7. **返回 bool**：验证通过 → `True`，任何失败 → `False`

---

## 4. approval_hook 接口

### 4.1 函数签名

```python
def humanlink_approval(command: str, context: dict) -> bool:
    """
    OpenClaw approval_hook 的 HumanLink 实现。

    Args:
        command: 原始命令字符串（如 "rm -rf /important"）
        context: 工具调用上下文，见 §4.2

    Returns:
        True  — 授权成功，OpenClaw 允许执行
        False — 授权失败或超时，OpenClaw 拒绝执行
    """
```

### 4.2 context 字段规范

OpenClaw 必须在 `context` 中提供以下字段：

| 字段 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `tool` | string | ✅ | 工具名称（如 `"bash"`, `"file_write"`, `"http_request"`） |
| `params` | dict | ✅ | 工具参数（字典）。**必须是真实解析到的参数，不是 Agent 描述的参数** |
| `risk_level` | string | ✅ | 风险等级：`"high"` / `"medium"` / `"low"` |
| `display_summary` | string | ⚪️ 建议 | 给用户看的操作摘要（≤256 字符），缺省时由 SDK 自动格式化 |
| `session_id` | string | ⚪️ 建议 | 会话 ID，用于审计关联 |
| `agent_id` | string | ⚪️ | Agent 标识符，仅审计用，不参与签名 |

**示例：**

```python
context = {
    "tool": "bash",
    "params": {"cmd": "rm -rf /home/user/important"},
    "risk_level": "high",
    "display_summary": "删除目录 /home/user/important",
    "session_id": "sess-abc123"
}
```

### 4.3 Challenge 构造（PC SDK 内部）

PC SDK 从 `context` 构造 Challenge：

```python
def _build_challenge(context: dict) -> dict:
    nonce = secrets.token_hex(8)   # 8 bytes = 16 hex chars

    # params 按字典序排列，拼接为 actionHash 输入
    sorted_params = dict(sorted(context["params"].items()))

    action_hash = build_action_hash(
        action=context["tool"],
        params=sorted_params,
        nonce=nonce,
        required_issuer_did=config["device"]["did"]
    )

    return {
        "origin": "local://openclaw",
        "action": context["tool"],
        "requiredIssuerDID": config["device"]["did"],
        "actionHash": action_hash,
        "nonce": nonce,
        "issuedAt": datetime.now(timezone.utc).isoformat(),
        "display": {
            "title": context.get("display_summary", context["tool"])[:64],
            "summary": context.get("display_summary", str(context["params"]))[:256],
            "risk": context.get("risk_level", "high"),
            "source": "local://openclaw"
        }
    }
```

### 4.4 USB Serial 下发（PC SDK → 设备）

```python
usb_cmd = {
    "cmd": "auth",
    "h_doc": compute_h_doc(assertion_skeleton).hex(),   # hex64
    "nonce": challenge["nonce"],                        # hex16
    "display": {
        "title": challenge["display"]["title"],
        "risk": challenge["display"]["risk"]
    }
}
client.send(json.dumps(usb_cmd) + "\n")
```

### 4.5 返回值与异常处理

```python
def humanlink_approval(command: str, context: dict) -> bool:
    challenge = _build_challenge(context)

    try:
        assertion = client.request_auth(challenge=challenge, timeout_seconds=30)
    except TimeoutError:
        _log("HumanLink: 用户未在 30s 内响应")
        return False
    except DeviceNotConnected:
        return _fallback_approval(command, context)

    result = verifier.verify(assertion=assertion, challenge=challenge)

    if not result.valid:
        _log(f"HumanLink 验证失败: step={result.failure_step} reason={result.failure_reason}")
        return False

    _write_audit(
        command=command,
        context=context,
        assertion_id=assertion["id"],
        device_did=result.device_did,
        chain_checked=result.chain_checked
    )

    return True
```

---

## 5. PC SDK 对外接口

### 5.1 HumanLinkVerifier

```python
class HumanLinkVerifier:
    def __init__(self, config_path: str):
        """
        加载 ~/.humanlink/config.yaml：
          device.did、verification.*、audit.log_path
        """

    def create_challenge(
        self,
        action: str,
        action_params: dict,
        display_title: str,
        display_summary: str,
        risk: str,
        origin: str = "local://openclaw"
    ) -> dict:
        """
        生成 Challenge dict，包含：
          actionHash（按 hash_construction.md §1）
          nonce（8 bytes random）
          requiredIssuerDID（从 config 读取）
          display 字段
        """

    def verify(
        self,
        assertion: dict,
        challenge: dict
    ) -> VerificationResult:
        """
        执行 verification_spec.md 定义的 10 步校验。
        返回 VerificationResult（valid, failure_step, failure_reason, ...）
        """
```

### 5.2 HumanLinkClient

```python
class HumanLinkClient:
    def __init__(self, transport: str = "usb", port: str = None, baud: int = 115200):
        """
        transport: "usb"（USB Serial，当前支持）
        port: 串口路径，None 时自动检测（扫描 /dev/ttyUSB* 或 COM*）
        """

    def connect(self) -> None:
        """
        建立 USB Serial 连接，等待设备 ready 事件。
        收到 ready 后触发 on_device_ready 回调（用于链上注册）。
        """

    def request_auth(
        self,
        challenge: dict,
        timeout_seconds: int = 30
    ) -> dict:
        """
        向设备发送 auth 命令，等待签名响应。
        返回设备响应 dict（status, matched_id, score, sensor_serial,
                         nonce, signed_hash, sig, pubkey）。
        Raises:
            TimeoutError: 超时
            DeviceNotConnected: 设备断开
            DeviceAuthError: 设备返回 status=err
        """

    def get_device_did(self) -> str:
        """
        从已连接设备获取 device_did。
        优先使用 ready 事件中的 DID，否则发送 getDID 命令。
        """

    def disconnect(self) -> None: ...

    # 事件回调
    on_device_ready: Callable[[str], None]   # device_did
    on_device_disconnected: Callable[[], None]
```

### 5.3 on_device_ready 与链上注册

设备接入时自动触发，SDK 负责判断是否需要注册：

```python
def _on_device_ready(device_did: str):
    """
    每当设备接入 SDK 时触发：
    1. 更新本地 config device.did
    2. 若设备未上链注册，触发异步注册
    """
    if config["device"]["did"] != device_did:
        config["device"]["did"] = device_did
        config.save()
        logger.info(f"Device DID updated: {device_did}")

    # 异步检查是否已在链上注册
    if network_available() and config["chain"]["auto_register"]:
        _register_if_needed(device_did)

def _register_if_needed(device_did: str):
    """调用 IssuerRegistry.registerIssuer() 和 UserDeviceRegistry.bindDevice()"""
    if not issuer_registry.isValidIssuer(device_did):
        pubkey_bytes = client.get_pubkey()
        attestation_hash = _hash_attestation(config["device"]["attestation"])
        issuer_registry.registerIssuer(pubkey_bytes, device_did, attestation_hash)
        logger.info(f"Device registered on-chain: {device_did}")
```

---

## 6. OpenClaw 配置

```yaml
# openclaw config（在原有配置中追加）

approval:
  provider: "humanlink"
  humanlink:
    config: "~/.humanlink/config.yaml"
    fallback: "deny"
    # deny  — 设备未连接时拒绝（推荐）
    # ui    — 降级到 OpenClaw 原有 UI 确认
    # allow — 允许执行（仅限受控开发环境）

  elevated_bypass: true  # elevated: full 时跳过 HumanLink 审批

tools:
  exec:
    default: "prompt"
  file_write:
    default: "prompt"
    risk_level: "high"
```

---

## 7. HumanLink SDK 配置

```yaml
# ~/.humanlink/config.yaml

device:
  did: "did:key:z6MkUser..."          # 首次注册后由 SDK 自动填写
  registered_at: "2025-06-14T09:00:00Z"
  attestation:
    sensorType: "optical_fingerprint"
    sensorFAR: 0.00001
    sensorFRR: 0.01
    secureElement: "ATECC608A"
    livenessDetection: false

hardware:
  transport: "usb"
  serial_port: null                    # null = 自动检测
  baud: 115200

verification:
  chain_check: "optional"             # required | optional | skip
  max_age_seconds: 30
  min_match_score: 100
  trust_policy: "default"

chain:
  network: "sepolia"
  auto_register: true                 # 设备接入时自动上链注册

audit:
  log_path: "~/.humanlink/audit.log"
  retention_days: 90
```

---

## 8. 错误处理对照表

| 场景 | PC SDK 行为 | OpenClaw 收到 | 建议用户体验 |
|------|------------|--------------|------------|
| 用户 30s 内未按指纹 | raise TimeoutError | `False` | "授权超时，操作已拒绝" |
| 指纹不匹配 | raise DeviceAuthError(code=2) | `False` | "指纹识别失败，操作已拒绝" |
| 设备未连接 | raise DeviceNotConnected | `False`（或 fallback） | "HumanLink 设备未连接" |
| ECDSA 验签失败 | result.valid=False, step=9 | `False` | "签名验证失败，操作已拒绝" |
| nonce 重放检测 | result.valid=False, step=5 | `False` | "检测到重放攻击，操作已拒绝" |
| 设备未注册（链上） | result.valid=False, step=10 | `False` | "设备未在链上注册，操作已拒绝" |
| 网络不可用（可选链验） | 降级，chain_checked=False | `True`（如本地验证通过） | 审计记录中标注 chain_check=skipped |

---

## 9. 时序图：完整本地授权流程

```
Agent          OpenClaw          PC SDK                设备
  │                │                │                    │
  │  工具调用       │                │                    │
  │────────────────▶                │                    │
  │                │                │                    │
  │           policy 拦截            │                    │
  │           approval_hook()       │                    │
  │                │                │                    │
  │                │  create_challenge(action, params)   │
  │                │────────────────▶                    │
  │                │                │                    │
  │                │                │ {"cmd":"auth",     │
  │                │                │  "h_doc": ...,     │
  │                │                │  "nonce": ...}     │
  │                │                │───────────────────▶│
  │                │                │                    │
  │                │                │            用户按指纹
  │                │                │            matched_id, score
  │                │                │            ATECC608A.sign()
  │                │                │                    │
  │                │                │  {"status":"ok",   │
  │                │                │   "sig": ...,      │
  │                │                │   "nonce": ...}    │
  │                │                │◀───────────────────│
  │                │                │                    │
  │                │  verifier.verify(assertion, challenge)
  │                │                │                    │
  │                │  result.valid=True                  │
  │                │◀────────────────                    │
  │                │                │                    │
  │         True   │                │                    │
  │◀───────────────│                │                    │
  │                │                │                    │
  │  工具执行       │                │                    │
```

---

## 10. 设备接入与 DID 链上注册时序

```
PC SDK 启动
  │
  ├─── 监听 USB 串口
  │
设备接入（USB 插入）
  │
  ├─── 设备发送 ready 事件（含 device_did）
  │
  ├─── on_device_ready(device_did) 回调
  │
  ├─── 检查 device_did ≠ config.device.did ?
  │       └─ 是：更新本地 config，记录变更日志
  │
  ├─── config.chain.auto_register = true ?
  │       └─ 是：检查 issuer_registry.isValidIssuer(device_did)
  │               └─ 未注册：调用 registerIssuer()
  │                          调用 userDeviceRegistry.bindDevice()
  │                          记录注册完成日志
  │
  └─── 设备就绪，等待 OpenClaw approval_hook 调用
```
