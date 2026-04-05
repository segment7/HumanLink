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
## 文件简明结构

```
humanlink/
humalink/
├── doc/                               ← 模块参数说明书
├── protocol/                          ← 协议栈设计
├── sdk/                               ← HumanLink SDK（守护进程 + 验证器）
├── firmware/                          ← ESP32 固件 (C++)
├── README.md                          ← 项目主说明
└── demo.md                            ← DEMO说明
```
---

**Why:** 项目是黑客松 Demo，需要端到端跑通 HumanLink 协议。
**How to apply:** SDK 在 `sdk/`，固件在 `firmware/`。守护进程入口是 `sdk/api/run_server.py`。

## Demo 实现架构

> ESP32 U盾（ESP32-WROOM + JM-101 + ATECC608A）是 HumanLink 协议的第一个 HAI 实现实例。U盾通过 USB Serial 插入 PC，PC 运行 HumanLink SDK 守护进程——协议端到端跑通。
> 

### 硬件架构

```
┌─────────────────── 硬件证明层 / TEE (Secure Enclave) ───────────────────────┐
│                                                                             │
│  [JM-101 指纹] <── UART ──> [ESP32 微控制器] <── I2C ──> [ATECC608A 芯片]  │
│    (智能模组)               (局部大脑)                   (硬件私钥黑盒)      │
│  输出: 匹配ID与得分          拼接哈希 H_final            ECDSA P-256 签名   │
│  (生物特征不出模块)          (ID+得分+SN+H_doc)                             │
│                                                                             │
└──────────────────────────────↑──┼──────────────────────────────────────────┘
       输入：挑战值哈希 H_doc    │  │   输出: 芯片硬件签名 (sig)
                                │  ↓
┌──────────────────── 用户本机 (PC/Mac/Linux) ────────────────────────┐
│                                                                    │
│  [Agent / OpenClaw]   [云端 Challenge（WebSocket）]             │
│          │                          │                              │
│          └──────────────┬───────────┘                              │
│                         ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  HumanLink SDK 守护进程（Python）                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

#### 接线

```
- 电路图/接线图：
ESP32-WROOM-32          JM-101                ATECC608A
──────────────          ──────                ─────────
GPIO17──────────────── RX (Pin3)
GPIO16──────────────── TX (Pin2)
3.3V ───────────────── VCC (Pin1)
GND ────────────────── GND (Pin4)
GPIO21 (SDA) ────────────────────────────────── SDA
GPIO22 (SCL) ────────────────────────────────── SCL
3.3V ────────────────────────────────────────── VCC
GND ─────────────────────────────────────────── GND

USB-Serial 芯片（CH340 / CP2102）
  → USB Type-A 插头，接主机 PC
  → 主机侧识别为 /dev/ttyUSB0（Linux）或 COM3（Windows）
```

#### 角色分工

| 组件 | 型号 | 角色 | 接口 |
| --- | --- | --- | --- |
| 主机（SDK 宿主） | 任意 PC/Mac/Linux | 运行 HumanLink SDK 守护进程：Assertion 组装、H_doc 计算、签名注入、链上交互、API 服务 | — |
| 微控制器 | ESP32-WROOM-32 | 安全飞地控制器：USB 串口接收 H_doc、调度传感器和安全芯片、返回签名 | USB Serial↔PC |
| 指纹传感器 | JM-101 (FPM383C 兼容) | 光学指纹采集与本地模板匹配，生物数据不出模块 | UART↔ESP32 |
| 安全芯片 | Microchip ATECC608A | 设备私钥存储，ECDSA P-256 签名，私钥不可读出 | I2C↔ESP32 |
| USB-Serial 芯片 | CH340 / CP2102 | U盾与主机 PC 的物理通信桥梁 | USB↔ESP32 |

#### 传感器技术参数（JM-101）

| 参数 | 数值 |
| --- | --- |
| 有效像素 | 256×288 |
| 分辨率 | 500 DPI |
| FAR（误识率） | < 0.001% |
| FRR（拒真率） | < 1% |
| 识别时间 | < 1 秒 |
| 搜索时间 | < 0.5 秒 |
| 模板容量 | 150 枚 |
| 通信 | UART 57600bps, 8N2 |
| 工作电压 | 3.0V – 3.6V |
| 工作电流 | 40–60mA |
| 触摸感应 | Touch 引脚高电平有效，待机 < 10μA |

#### JM-101 关键命令

| 场景 | 命令 | 码 | 说明 |
| --- | --- | --- | --- |
| 操作员注册 | PS_AutoEnroll | 31H | 一站式：多次采集→特征→模板→存储。bit4 控制是否允许重复 |
| 每次认证 | PS_AutoIdentify | 32H | 一站式：采集→特征→搜索。ID=0xFFFF 为 1:N 全库搜索。返回 matched_id + score |
| 芯片序列号 | GetChipSN | 34H | 32 字节唯一序列号，用于签名绑定 |
| 取消 | PS_Cancel | 30H | 超时或用户拒绝时终止采集 |
| 模板数量 | PS_ValidTempleteNum | 1DH | 查询已注册指纹数 |
| 删除模板 | PS_DeletChar | 0CH | 移除指定槽位 |
| 休眠 | PS_Sleep | 33H | 低功耗，Touch 唤醒 |

### 软件架构

**开发环境**

| 组件 | 环境 |
| --- | --- |
| ESP32 固件 | PlatformIO + Arduino Framework, C++ |
| PC SDK 守护进程 | Python 3.11+, FastAPI, uvicorn（Windows/Mac/Linux 通用） |
| 链上合约 | Solidity 0.8.x, Hardhat, Sepolia |
| HumanLink SDK | Python 3.11+ |

**第三方库**

ESP32 固件：`ArduinoECCX08`（I2C 驱动）、`mbedtls`（SHA256，ESP-IDF 内置）、 `jm101`（UART 协议驱动）

PC SDK：`fastapi` + `uvicorn`（API / 守护进程）、`pyserial`（USB Serial 通信）、`ecdsa`（签名验证）、`pyld`（JSON-LD 规范化）、`web3.py`（链上交互）、`sqlite3`（本地存储）、`websockets`（云端场景接收云端 Challenge）

#### PC SDK 守护进程架构

```
┌─────────────────────────────────────────────────────────┐
│  core（Python 守护进程，运行在 PC/Mac/Linux）             │
│                                                         │
│  ┌────────────┐ ┌────────────┐ ┌──────────────────┐     │
│  │ USB Bridge │ │ DID Engine │ │ Assertion Builder│     │
│  │ send H_doc │ │ pk→did:key │ │ build_skeleton() │     │
│  │ recv sig   │ │ DID Doc    │ │ canonicalize()   │     │
│  │ recv match │ │            │ │ inject_proof()   │     │
│  └────────────┘ └────────────┘ └──────────────────┘     │
│         └──────────────┴────────────────┘                │
│                   Event Bus                              │
├─────────────────────────────────────────────────────────┤
│  api（FastAPI）localhost:8765                            │
│                                                         │
│  POST /auth/challenge    ← 接收含 requiredIssuerDID 的 challenge │
│  GET  /auth/status       ← 会话状态                      │
│  GET  /device/did        ← 设备 DID Document             │
│  GET  /device/attestation← 硬件资质                      │
│  POST /assertion/revoke  ← 撤销断言                      │
├─────────────────────────────────────────────────────────┤
│  ws_client（仅用于云端）                                     │
│  · 连接云端 WebSocket，接收 Challenge                     │
│  · 回传 Assertion 给云端 Verifier                         │
├─────────────────────────────────────────────────────────┤
│  存储（SQLite）                                          │
│  · did_store       设备 DID + 公钥                       │
│  · session_log     认证事件日志                           │
│  · revoke_list     已撤销断言哈希                        │
└─────────────────────────────────────────────────────────┘
```

---

### HumanLink 本地设计：本地 Agent + AI Gateway 集成

> 针对 Agent 跑在用户自己机器上、无中心服务器的场景。
> 

#### 场景定义

```
用户自己的机器
┌──────────────────────────────────────────────────────┐
│                                                      │
│  [Agent 进程]                                        │
│       ↓ 发起命令                                     │
│  [AI Gateway / OpenClaw]   ← 本地安全护栏            │
│       ↓ 需要人类确认时                               │
│  [HumanLink SDK（本地）]    ← 人类授权证明            │
│       ↓                                              │
│  [HumanLink 设备]          ← 物理在场确认            │
│    USB / Bluetooth                                   │
│                                                      │
└──────────────────────────────────────────────────────┘

无中心服务器、无云端验证依赖
```

#### **核心差异（vs 云端场景）**：

|  | 云端 平台 | 本地 |
| --- | --- | --- |
| Challenge 生成方 | 云端平台服务器 | 本地 OpenClaw |
| 用户-设备绑定存储 | 平台 DB / 链上 | 本地配置文件 / 链上 |
| 验证执行位置 | HumanLinkVerifier（云端部署） | HumanLinkVerifier（本机运行） |
| 链上检查 | 必须 | 可选（降级为本地信任） |
| 举证对象 | 平台向第三方举证 | 用户向应用/审计方自证 |

#### 与 OpenClaw 的集成

OpenClaw 的执行审批流程本身已有三层护栏：

```
Policy 检查 → Allowlist 检查 → （可选）用户审批提示
```

HumanLink 作为第四层，挂载在**用户审批提示**这个扩展点上：

```
Policy 检查
    ↓ 通过
Allowlist 检查
    ↓ 通过
执行审批触发
    ↓ 需要人类确认（elevated ≠ full）
    ├── 原有路径：UI 提示点击确认（软件层，可伪造）
    └── HumanLink 路径：物理生物特征确认（密码学证明，不可伪造）
    ↓
命令执行
```

OpenClaw 侧只需在审批钩子里调用 HumanLink 本地 SDK，无需改动 Policy / Allowlist 逻辑。

#### OpenClaw 集成实现

#### 审批钩子

```python
# openclaw_humanlink_hook.py
# 挂载到 OpenClaw 的 approval_hook 扩展点

from humanlink_sdk import HumanLinkVerifier, HumanLinkClient

verifier = HumanLinkVerifier(
    config_path="~/.humanlink/config.yaml"
)
client = HumanLinkClient(transport="usb")  # 或 "bluetooth"

def humanlink_approval(command: str, context: dict) -> bool:
    """
    OpenClaw approval_hook 的 HumanLink 实现。
    返回 True = 允许执行，False = 拒绝。

    替代原有的 UI 点击确认，生成密码学授权记录。
    """

    # 1. 生成 Challenge（本地，无需服务器）
    challenge = verifier.create_challenge(
        action=context["tool"],
        action_params=context["params"],
        display_title="命令执行确认",
        display_summary=_format_summary(command, context),
        risk=context.get("risk_level", "high"),
        origin="local://openclaw"   # 本地来源标识
    )

    # 2. 推送到连接的 HumanLink 设备
    try:
        assertion = client.request_auth(
            challenge=challenge,
            timeout_seconds=30
        )
    except TimeoutError:
        # 用户未响应 → 按 OpenClaw ask_fallback 策略处理（默认 deny）
        return False
    except DeviceNotConnected:
        # 设备未连接 → 降级到 OpenClaw 原有 UI 审批或 deny
        return _fallback_approval(command, context)

    # 3. 本地验证（步骤 1-9，可选步骤 10）
    result = verifier.verify(assertion=assertion, challenge=challenge)

    if not result.valid:
        _log(f"HumanLink 验证失败: {result.failure_reason} (step {result.failure_step})")
        return False

    # 4. 写本地审计记录
    _write_audit(
        command=command,
        assertion_id=assertion["id"],
        device_did=result.device_did,
        chain_checked=result.chain_checked,  # 是否完成链上校验
        timestamp=assertion["created"]
    )

    return True

def _format_summary(command: str, context: dict) -> str:
    """将 OpenClaw 解析到的真实命令参数格式化为用户可读摘要"""
    tool = context.get("tool", "未知操作")
    params = context.get("params", {})
    return f"{tool}: {command[:100]}"  # 截断过长命令
```

#### OpenClaw 配置侧

```yaml
# openclaw config（在原有配置中追加）

tools:
  exec:
    default: "prompt"       # 需要审批

approval:
  provider: "humanlink"     # 替换默认 UI 审批
  humanlink:
    config: "~/.humanlink/config.yaml"
    fallback: "deny"        # 设备未连接时的降级策略
    # deny    — 设备未连接时拒绝（推荐）
    # ui      — 降级到 OpenClaw 原有 UI 确认
    # allow   — 允许执行（仅限受控开发环境）

  # elevated: full 时跳过所有审批（含 HumanLink），保持原有 OpenClaw 行为
  elevated_bypass: true
```

#### 本地架构

```
┌────────────────────────── 用户本机 ──────────────────────────────┐
│                                                                  │
│  ┌─────────────┐                                                 │
│  │  Agent 进程  │                                                 │
│  │  (任意框架)  │                                                 │
│  └──────┬──────┘                                                 │
│         │ 命令 / 工具调用                                         │
│         ▼                                                        │
│  ┌──────────────────────────────────────────┐                   │
│  │  OpenClaw（本地 AI Gateway）              │                   │
│  │                                          │                   │
│  │  ┌──────────┐  ┌──────────┐             │                   │
│  │  │  Policy  │  │Allowlist │             │                   │
│  │  └────┬─────┘  └────┬─────┘             │                   │
│  │       └─────────────┘                   │                   │
│  │                 ↓ 需要审批               │                   │
│  │  ┌──────────────────────────────────┐   │                   │
│  │  │  执行审批钩子                     │   │                   │
│  │  │  approval_hook(command, context) │   │                   │
│  │  │                                  │   │                   │
│  │  │  if requires_humanlink(command): │   │                   │
│  │  │    → 调用 HumanLink 本地 SDK     │   │                   │
│  │  └──────────────────────────────────┘   │                   │
│  └──────────────────────┬───────────────────┘                   │
│                         │    api（FastAPI）localhost:8765                                      │
│                         ▼                                        │
│  ┌──────────────────────────────────────────┐                   │
│  │  HumanLink SDK（HumanLinkVerifier）       │                   │
│  │                                          │                   │
│  │  · 从本地配置读取 requiredIssuerDID       │                   │
│  │  · 生成 Challenge（本地，无需服务器）      │                   │
│  │  · 本地 ECDSA 验签                       │                   │
│  │  · 链上检查（可选，有网时执行）            │                   │
│  │  · 生成本地审计记录                       │                   │
│  └──────────────────────┬───────────────────┘                   │
│                         │ USB                                   │
│                         ▼                                        │
│  ┌──────────────────────────────────────────┐                   │
│  │  HumanLink 设备                          │                   │
│  │   用户按指纹 · 签名                       │                   │
│  └──────────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
                         ↕ 可选联网
                    ┌─────────────────────┐
                    │  链上（Sepolia）     │
                    │  · IssuerRegistry   │
                    │  · 断言撤销状态     │
                    └─────────────────────┘
```

#### 本地验证模式

#### 分级验证与本地设备绑定

```yaml
# ~/.humanlink/config.yaml
device:
  did: "did:key:z6MkUser..."
  registered_at: "2025-06-14T09:00:00Z"
  attestation_hash: "sha256(...)"
  
verification:
  chain_check: "optional"
  # required — 强制联网验证
  # optional — 有网则查，无网跳过并在审计记录中标注（云端推荐）
  # skip     — 纯离线，仅本地验签

  max_age_seconds: 30
  min_match_score: 100
  
audit:
  log_path: "~/.humanlink/audit.log"
  retention_days: 90
```

| 步骤 | 内容 | 是否需要联网 |
| --- | --- | --- |
| 1–9 | 结构校验、设备绑定、actionHash、origin、nonce、时间窗口、matchScore、attestation、ECDSA 签名 | **否** |
| 10 | isValidIssuer() + isRevoked() | **是（可选降级）** |

纯离线时，步骤 1–9 全部本地完成，可正常拦截。步骤 10 降级为本地信任，审计记录中自动打标：`"chain_check": "skipped_offline"`。

#### 本地审计记录

无中心服务器时，审计记录写本地，格式与云端审计库兼容，可在需要时导出举证：

```json
{
  "audit_version": "1.0",
  "record_id": "urn:uuid:...",
  "timestamp": "2025-06-14T10:23:00Z",
  "command": "rm -rf /important",
  "tool": "bash",
  "params": { "cmd": "rm -rf /important" },
  "assertion_id": "urn:uuid:550e8400...",
  "device_did": "did:key:z6MkUser...",
  "match_score": 188,
  "chain_checked": false,
  "chain_check_reason": "skipped_offline",
  "openclaw_policy": "prompt",
  "result": "approved",
  "signature": "本地审计记录签名（设备私钥）"
}
```

**`chain_checked: false` 的含义**：本次授权完成了本地密码学验证（步骤 1-9），但未完成链上吊销检查。用户知晓该设备当时未被吊销，但无法排除设备已吊销但网络不可达的极端情况。审计时应标注此字段。

#### 设备初始化流程

本地场景设备绑定存在本地：

```
首次配置（一次性）：
  用户插入 HumanLink 设备
    → SDK 读取设备 DID（did:key:zUser）
    → 写入本地配置文件 ~/.humanlink/config.yaml
    → 可选：同步注册到链上 UserDeviceRegistry

运行时：
  OpenClaw 触发审批
    → HumanLink SDK 读取本地配置
    → requiredIssuerDID = config.device_did
    → 生成 Challenge，推送给连接的设备
    → 设备自验 DID 一致 → 执行认证
```

#### 安全边界说明

| 问题 | 本地场景的处理 |
| --- | --- |
| 设备被盗后仍能签名 | 链上 revokeIssuer() 有效；offline 时无法实时检查，建议定期联网同步吊销列表 |
| 本地配置文件被篡改 | requiredIssuerDID 被改 → 设备自验 DID 不一致 → 设备拒绝响应 |
| Agent 绕过 OpenClaw 直接调用系统 | OpenClaw 沙箱隔离职责，与 HumanLink 无关 |
| 审计记录被删除 | 本地记录可选同步到链上 AuditLog；删除记录本身可被发现（记录有序列号） |
| elevated: full 时跳过 HumanLink | 这是 OpenClaw 原有设计，HumanLink 尊重该配置，需用户显式设置 |

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
10. 链上校验：isValidIssuer() + isRevoked()（可选）

---
