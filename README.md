# HumanLink — Agent 人类授权基础设施

> **一句话定义**：AI Agent 时代的人类在场授权基础设施，让任何人在任何 Agent 执行高风险操作前，留下密码学级别的不可伪造授权记录。
> 

类比：MCP 定义了 Agent 如何调用工具，HumanLink 定义了 Agent 执行高风险操作前如何留下不可伪造的人类授权记录。

## 一、项目概述

### 问题：Agent 时代的授权黑洞

2025—2026 年，Agent 已经在替用户转账、发邮件、删文件、操作设备。出事后，三方都没有可独立核验的证据：

```
用户：  "我的 Agent 把 $5000 转给了陌生人，我没授权过！"
平台：  "我们有操作日志。"
用户：  "日志是你们自己写的，谁知道真不真。"
─────────────────────────────────────────────────
个人用户也面临同样困境：
用户：  "我的 Agent 帮我删了那个文件，但我不记得我同意了"
应用：  "你点了确认按钮。"
用户：  "能证明点按钮的是我本人吗？万一我的 Agent 被劫持了呢？"
```

现有的"授权"只是软件 token——会话状态、UI 点击埋点、操作日志。这些证据的共同弱点：**都由平台单方生成，用户无法独立核实，监管机构无法独立审计，法律上无法举证。**

HumanLink 解决的是"执行的那一刻，有没有留下真人物理授权的密码学证明"。

### 定位：Agent 时代的人类授权基础设施

| 类比 | 解决什么 | 核心产品 | 谁付费 |
| --- | --- | --- | --- |
| MCP | Agent 怎么调用工具 | 协议 + SDK | Agent 开发者 |
| AI Gateway | Agent 流量路由和管控 | 策略引擎 + API | 平台运营商 |
| **HumanLink** | **Agent 执行前如何留下不可伪造的人类授权记录** | **协议 + SDK** | **Agent 平台（云端集成）/ 个人用户（本地集成）** |

Agent 平台集成 HumanLink，用户每次授权高风险操作都会生成一份**密码学断言**：绑定了具体操作参数、由用户的物理生物特征触发、由防篡改安全芯片签名、可链上核验。

出事后，平台拿出这份断言，链上验证一行代码，证明链完整：**"这个操作，在这个时刻，有一个已注册的人类物理在场并主动确认了。"**

### 核心设计原则

**一次按压 = 一份断言 = 一次授权，不缓存，不复用。**

每一次物理按压转化为一份密码学断言（Assertion），直接绑定触发它的具体操作。断言即用即弃，无 TTL，无复用窗口。人在场（Present）本身就是授权的物理证据。

### 当前实现形态：HumanLink U盾 + 开放协议

当前的ESP32 U盾形态【ESP32 + JM-101 + ATECC608A 方案】是 **参考实现（Reference Implementation）**，通过 USB 串口插入任意 PC/Mac 即可使用。PC 上运行 HumanLink SDK（Python 守护进程），负责组装 Assertion、计算 H_doc，并通过 USB Serial 与 U盾通信。

最终产品形态是可嵌入任何设备的开放基础设施——OEM 厂商实现 HumanLink 的硬件抽象接口（HAI），即可成为合规的 Assertion 签发设备。

未来 HAI 实现示意：

- 企业笔记本 TEE + 指纹 → HumanLink Issuer
- 手机安全芯片 + Face ID → HumanLink Issuer
- 工控面板 + 虹膜模块 → HumanLink Issuer

### 商业模式

HumanLink 是开放协议，不是封闭产品，面向本地和云端提供不同接入路径。

|  | **本地用户** | **云端集成** |
| --- | --- | --- |
| **核心场景** | 个人 Agent 助手、消费者应用 | Copilot/Cursor 类平台、企业私有 Agent |
| **接入方式** | 本地 HumanLink SDK + AI Gateway（如 OpenClaw）直连 | HumanLink SDK 集成（本机运行或服务端部署均可） |
| **设备注册** | 用户自主注册，绑定至个人账号 | 平台管理员注册，绑定至用户账号 |
| **举证主体** | 用户本人可举证 | 平台可代用户举证 |
| **付费模式** | 硬件设备 + 增值服务订阅 | SDK 按验证次数收费 |

#### **Agent 云端平台为什么愿意付费？**

当前的替代方案是"什么都没有"或"自建软件埋点"。自建方案：

- 用户不信任（"你自己写的日志"）
- 监管不认可（无第三方密码学证明）
- 法律上站不住脚（无物理在场证明）

HumanLink 给平台的是**可在任何纠纷中独立核验的密码学授权证明**，是未来 Agent 平台的基础设施标配。

**短期**：HumanLink SDK 按验证次数向 Agent 平台收费。高风险操作（转账、删除、发布）每次验证付费。

**中期**：企业合规方案。SDK + 审计面板 + 参考硬件打包，年费订阅。

**长期**：信任基础设施层。Agent 平台标配 HumanLink，如同网站标配 HTTPS。OEM 通过 HAI 认证扩大 Issuer 网络。

### 竞品空白

| 竞品方向 | 代表 | 它解决的 | 它解决不了的 |
| --- | --- | --- | --- |
| Agent 支付协议 | Visa TAP, Stripe ACP | Agent 有没有**权限** | 执行时有没有**人类物理在场** |
| 软件 HITL 工具 | Permit.io, Auth0 CIBA | 有没有**软件层确认** | 确认的是不是**真人**，证据能不能举证 |
| 审计合规平台 | FireTail, Zenity | Agent **做了什么** | 有没有**人类同意**，同意记录是否可独立核验 |
| Proof of Personhood | Worldcoin | **注册时**是人 | **此刻执行时**在不在场 |
| 设备生物认证 | Apple Touch ID | 是不是**设备主人** | 跨平台操作绑定、链上可审计 |

HumanLink 填的空白：**此刻物理在场 + 操作绑定 + 密码学可举证 + 链上可审计 + 开放协议**。

---

## 二、业务流程图

### 本地流程（AI Gateway 集成）

本地PC 跑 Agent + OpenClaw，U盾插 USB，本地闭环。

```
Agent               OpenClaw（本地）         HumanLink SDK（本地）    设备
  │                      │                         │                   │
  │ 执行命令请求          │                         │                   │
  │ rm -rf /important    │                         │                   │
  │ ────────────────────▶│                         │                   │
  │                      │                         │                   │
  │                      │ Policy 检查 ✓           │                   │
  │                      │ Allowlist 检查 ✓        │                   │
  │                      │ → 需要审批              │                   │
  │                      │                         │                   │
  │                      │ approval_hook()         │                   │
  │                      │ ───────────────────────▶│                   │
  │                      │                         │                   │
  │                      │                         │ 读本地配置         │
  │                      │                         │ requiredDID=zUser │
  │                      │                         │                   │
  │                      │                         │ 生成 Challenge     │
  │                      │                         │ actionHash 含 DID │
  │                      │                         │ ─────────────────▶│
  │                      │                         │                   │
  │                      │                         │          设备自验：│
  │                      │                         │          DID==zUser│
  │                      │                         │                   │
  │                      │                         │         屏幕显示：│
  │                      │                         │   ┌────────────┐  │
  │                      │                         │   │ 执行确认    │  │
  │                      │                         │   │ rm -rf     │  │
  │                      │                         │   │ /important │  │
  │                      │                         │   │ [按指纹]   │  │
  │                      │                         │   └────────────┘  │
  │                      │                         │                   │
  │                      │                         │         用户按指纹│
  │                      │                         │         → 签名    │
  │                      │                         │ ◀─────────────────│
  │                      │                         │                   │
  │                      │                         │ 本地验证步骤 1-9  │
  │                      │                         │ （可选步骤 10）   │
  │                      │                         │ → valid: true     │
  │                      │                         │                   │
  │                      │                         │ 写本地审计记录    │
  │                      │                         │                   │
  │                      │ True ◀──────────────────│                   │
  │                      │                         │                   │
  │                      │ 命令执行                │                   │
  │ 执行结果 ◀────────────│                         │                   │
```

```
┌──────────────── 用户本机 (PC/Mac) ────────────────┐
│                                                 │
│  [Agent] ──(试图删库)─▶ [OpenClaw (拦截)]        │
│                            │                    │
│                            ▼                    │
│                 [HumanLink 本地 SDK (Python)]    │
│                 · 组装 Challenge                │
│                 · 计算 H_doc = SHA256(骨架)     │
│                 · 组装最终 Assertion 并验签      │
│                            │                    │
└────────────────────────────┼────────────────────┘
                             │  USB 线 (串口直连)
                             │  传输: H_doc
                             ▼
┌────────────── 硬件外设 (ESP32 U盘形态) ─────────────┐
│                                                 │
│                 [ESP32-WROOM]                   │
│  调度通信 ◀──────────┼──────────▶ 硬件防伪       │
│                      │                          │
│                      ▼                          │
│         ┌─────────────────────────┐             │
│         │        [JM-101]         │  <-- 按指纹  │
│         │  比对成功 → 返回 ID+Score │             │
│         └─────────────────────────┘             │
│                      │                          │
│         ┌─────────────────────────┐             │
│         │       [ATECC608A]       │             │
│         │   签发 ECDSA 硬件签名     │             │
│         └─────────────────────────┘             │
└─────────────────────────────────────────────────┘
```

### 云端流程（Agent 平台集成）

PC 跑 SDK 守护进程，通过 WebSocket 接收云端 Challenge，转发给 U盾签名，回传 Assertion 给云端验证。IT 部门可通过 MDM（Intune/Jamf）一键推送守护进程到全公司设备，员工领一枚 U盾即可接入。

用户通过 Copilot 类 Agent 管理财务，Agent 日常自动执行低风险任务（整理收据、归档文件）。遇到高风险操作（转账 $500）时，Agent 平台拦截该调用并通过 HumanLink 获取真人物理确认，生成不可伪造的授权记录。出现纠纷时，平台可拿出此记录作为密码学级别举证。

```
┌───────────────────────── 云端 (Agent 平台) ──────────────────────────┐
│                                                                    │
│  1. Agent 发起高危操作 (转账)                                        │
│  2. 平台拦截，生成 Challenge (包含 requiredDID, actionHash)           │
│  3. 平台通过 WebSocket / HTTPS 推送 Challenge 到目标员工的电脑          │
│                                                                    │
└─────────────────────────────────┬──────────────────────────────────┘
                                  │ (互联网通信)
                                  ▼
┌──────────────────────── 员工本机 (PC/Mac) ─────────────────────────┐
│                                                                    │
│  [HumanLink Client 后台软件 (软件网关)]                             │
│  · 接收云端 Challenge                                                │
│  · 将 Challenge 解析为 H_doc                                         │
│  · 通过 USB 串口透传给硬件                                           │
│  · 接收硬件返回的 Signature，回传给云端                               │
│                                                                    │
└─────────────────────────────────┬──────────────────────────────────┘
                                  │ (USB 串口直连)
                                  ▼
┌────────────── 硬件外设 (ESP32 U盘形态 / HumanLink Issuer) ──────────┐
│                                                                    │
│  [ESP32] ──▶ 调度 JM-101 (指纹比对) ──▶ 调度 ATECC608A (私钥签名)    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

```
Agent            云端平台              员工 PC（SDK 守护进程）   U盾（ESP32）     链上
  │                  │                       │                   │            
  │ 0. API 调用      │                       │                   │            
  │ transfer($500)  │                       │                   │             
  │ ────────────────▶│                       │                   │           
  │                  │                       │                   │            
  │ (Agent 等待）    │ 1. 风险拦截            │                   │            
  │                  │    $500>阈值→认证      │                   │           
  │                  │                       │                   │            
  │                  │ 2. 查用户绑定 DID      │                   │            
  │                  │    → requiredDID       │                   │           
  │                  │                       │                   │            
  │                  │ 3. 生成 Challenge      │                   │           
  │                  │    requiredDID 嵌入    │                   │           
  │                  │    actionHash 含 DID   │                   │           
  │                  │                       │                   │            
  │                  │ 4. WebSocket 推送      │                   │           
  │                  │    Challenge 到员工 PC  │                   │          
  │                  │ ──────────────────────▶│                   │          
  │                  │                       │                   │            
  │                  │                       │ 5. 计算 H_doc     │            
  │                  │                       │    USB Serial 转发│            
  │                  │                       │ ─────────────────▶│           
  │                  │                       │                   │            
  │                  │                       │          6. 设备自验：          
  │                  │                       │          requiredDID==自身 ✓   
  │                  │                       │                   │            
  │                  │                       │         7. 弹出系统通知         
  │                  │                       │         "Agent 请求转账        
  │                  │                       │          请触碰 U盾确认"        
  │                  │                       │                   │            
  │                  │                       │         8. 用户按指纹          
  │                  │                       │            → ECDSA 签名        
  │                  │                       │ ◀─────────────────│           
  │                  │                       │                   │            
  │                  │                       │ 9. 组装 Assertion  │           
  │                  │ 10. 回传 Assertion     │                   │           
  │                  │ ◀─────────────────────│                   │           
  │                  │                       │                   │            
  │                  │ 11. 10 步验证          │                   │           
  │                  │  [2] device.id        │                   │            
  │                  │      ==requiredDID ✓  │                   │           
  │                  │  [3] actionHash ✓     │                   │           
  │                  │  [9] ECDSA ✓ ──────────────────────────▶ │
  │                  │  [10] isValidIssuer ✓ │                   │ 
  │                  │                       │                   │            
  │                  │ 12. 写入审计记录       │                   │            
  │                  │ 13. 执行操作           │                   │           
  │ 14. 返回结果     │                       │                   │            
  │ ◀────────────────│                       │                   │        
```

### 初始化流程

```
用户首次使用 HumanLink（本地 路径）

用户                   HumanLink App            链上
  │                        │                     │
  │ 1. 打开 App，选择绑定设备 │                     │
  │ ──────────────────────▶ │                     │
  │                        │ 2. 读取设备 DID       │
  │                        │    did:key:zAlice    │
  │                        │                     │
  │                        │ 3. 注册设备到链上     │
  │                        │ ───────────────────▶ │
  │                        │   IssuerRegistry     │
  │                        │   .registerIssuer()  │
  │                        │                     │
  │                        │ 4. 绑定账号↔设备      │
  │                        │   UserDeviceRegistry │
  │                        │   .bindDevice(       │
  │                        │     userId, deviceDID│
  │                        │   )                  │
  │                        │ ───────────────────▶ │
  │                        │                     │
  │ 5. 绑定完成            │                     │
  │ ◀────────────────────── │                     │
```

```
企业平台用户注册 HumanLink（云端 路径）

用户                   Agent 平台（Admin）
  │                        │
  │ 1. IT 为用户配发已注册    │
  │    上链的 HumanLink 设备  │
  │                        │
  │                        │ 2. 管理员绑定
  │                        │    用户 ID ↔ 设备 DID
  │                        │    到平台用户表
  │                        │
  │ 3. 用户在设备上注册指纹   │
  │ 4. 配置完成，可开始使用   │       
```

### 纠纷举证路径

```
纠纷场景一：用户否认授权（"我没让 Agent 转这笔钱"）
────────────────────────────────────────────────────
  平台审计库：assertion_id → challenge.actionHash
  → 链上核验：assertion_id 对应的设备是否注册，签名是否有效
  → HumanLink 设备日志：slot-03 在 10:23 物理按压确认了操作 X
  → 证明："有已注册用户在该时刻物理在场并确认了此操作"

纠纷场景二：Agent 幻觉执行了用户未意图的操作
────────────────────────────────────────────────────
  若用户拒绝了按指纹 → 操作未执行 → 平台有拒绝记录
  若用户按了指纹 → 用户屏幕上显示的是真实参数（平台填写）
  → 平台举证：用户在看到正确操作摘要后主动确认

纠纷场景三：监管审计（EU AI Act / SOX / HIPAA）
────────────────────────────────────────────────────
  链上记录：device_did + actionHash + timestamp（不含生物数据）
  平台内部：user_session → assertion_id → slot-03
  企业映射：slot-03 = 张三（HR 系统绑定）
  → 审计员可追溯到人，满足人类监督记录要求
```

---

## 三、整体架构图

```

           Reference Implementation（黑客松 Demo）

┌──────────────────── 用户本机 (PC/Mac/Linux) ─────────────────────┐
│                                                                  │
│  [Agent / OpenClaw / 云端 Challenge 接收]                        │
│              │                                                   │
│              ▼                                                   │
│  [HumanLink SDK 守护进程]                                         │
│  · 组装 Challenge / 计算 H_doc                                   │
│  · 组装 Assertion 骨架 / 注入签名                                 │
│  · 10 步验证 / 链上交互                                           │
│              │                                                   │
└──────────────┼───────────────────────────────────────────────────┘
               │  USB Serial（/dev/ttyUSB0 或 COM3）
               ▼
┌────────────────── 硬件层 (Secure Enclave) ──────────────────────┐
│                                                                │
│  [JM-101] ←UART→ [ESP32] ←I2C→ [ATECC608A]                   │
│  指纹传感器       微控制器        安全芯片                       │
│  ↓                ↓               ↓                             │
│  采集图像         特征哈希        ECDSA P-256 签名              │
│                  内存立即清零     私钥永不出芯片                 │
└────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════╗
║                  HumanLink Protocol（核心产品）                    ║
║                                                                   ║
║  ┌─ 接入层（云端 / 本地，同一套 SDK）───────────────────────────┐  ║
║  │                                                              │  ║
║  │  云端：高风险操作由 Agent 平台拦截，生成 Challenge，验证 Assertion    │  ║
║  │  本地：AI Gateway 触发审批，HumanLink SDK 本地生成 Challenge 并验签    │  ║
║  │                                                              │  ║
║  │  [Copilot] [Cursor] [企业 Agent]   [OpenClaw] [本地 Gateway] │  ║
║  │       │        │         │              │           │        │  ║
║  │       └────────┴─────────┴──────────────┴───────────┘        │  ║
║  │                              │                               │  ║
║  │           HumanLink SDK（统一验证接口）                       │  ║
║  │           · 生成 Challenge（含 requiredIssuerDID）             │  ║
║  │           · 验证 Assertion → 生成可举证授权记录                │  ║
║  │           · chain_check 配置决定步骤 10 是否执行               │  ║
║  │           · Agent 无权发起或绕过认证                          │  ║
║  └──────────────────────────────┬─────────────────────────────┘  ║
║                            │  HumanPresenceAssertion                ║
║  ┌─ 协议核心层 ─────────────┴────────────────────────────────────┐  ║
║  │                                                               │  ║
║  │  · Assertion 数据格式规范                                     │  ║
║  │  · Challenge 绑定（action + origin + nonce + requiredIssuerDID）│  ║
║  │  · actionHash 含设备公钥，防设备替换攻击                       │  ║
║  │  · 单签名结构（hardwareProof）                                │  ║
║  │  · 设备信任分级（attestation）                                │  ║
║  │                                                               │  ║
║  └──────────────────────────┬────────────────────────────────────┘  ║
║                            │                                        ║
║  ┌─ 身份与链上层 ────────────┴────────────────────────────────────┐  ║
║  │                                                               │  ║
║  │  · Device DID (did:key) — 链上 IssuerRegistry 注册            │  ║
║  │  · UserDeviceRegistry  — 用户账号 ↔ 设备 DID 绑定             │  ║
║  │  · AssertionStatusRegistry — 断言撤销                         │  ║
║  │  · AuditLog — 高危操作审计摘要（可选）                        │  ║
║  │                                                               │  ║
║  └──────────────────────────┬────────────────────────────────────┘  ║
║                            │                                        ║
║  ┌─ 硬件抽象接口 (HAI) ───┴───────────────────────────────────┐  ║
║  │                                                              │  ║
║  │  定义：一个合格的 HumanLink Issuer 必须实现的接口              │  ║
║  │  任何带生物传感器 + 安全芯片的设备都能实现                    │  ║
║  │  不规定具体硬件，只规定能力要求和输出格式                     │  ║
║  │  · get_device_did() → str                                   │  ║
║  │  · get_attestation() → dict   → 硬件资质证明                  │  ║
║  │  · authenticate(h_doc, required_did) → AuthResult            │ ║
║  │                                                              │  ║
║  └──────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 四、HumanLink SDK

`HumanLinkVerifier` 是 HumanLink 的核心组件，**本地和云端场景共用同一套 SDK**。两者的唯一差异是配置参数（`chain_check`、`origin`），不存在两套实现。PC 上运行的 SDK 守护进程（`sdk/api/server.py`）就是这套逻辑的运行时入口。

```python
# sdk/verifier.py

class HumanLinkVerifier:
    """
    核心验证器。任何接入方（本地 AI Gateway 或云端 Agent 平台）引入此 SDK
    即可生成 Challenge 并验证 Assertion。
    """

    def __init__(
        self,
        issuer_registry_address: str,
        user_device_registry_address: str,
        rpc_url: str,
        origin: str,                              # 本地填 "local://openclaw"；云端填平台域名
        min_match_score: int = 100,
        trust_policy: TrustPolicy = TrustPolicy.DEFAULT
        enforce_device_binding: bool = True
    ):
  
    def get_required_issuer_did(self, user_id: str) -> str:
    """
    从 UserDeviceRegistry（链上或本地 DB）取用户绑定的设备 DID。
    云端场景：优先从平台自有 DB 取，避免链上查询延迟。
    本地场景：从本地配置文件或链上 UserDeviceRegistry 取。
    """

    def create_challenge(
        self,
        user_id: str,
        action: str,
        action_params: dict,
        display_title: str,
        display_summary: str,
        risk: str = "high"
    ) -> Challenge:
        """
        生成 Challenge（本地和云端均调用此方法）。
        内部步骤：
          1. required_issuer_did = self.get_required_issuer_did(user_id)
          2. nonce = uuid4()
          3. actionHash = sha256(
               action ‖ sorted(action_params) ‖ nonce ‖ required_issuer_did
             )
          4. 返回含 requiredIssuerDID 的 Challenge 对象

        action_params: 接入方自己解析到的真实操作参数（非 Agent 描述）
        origin 自动填入 self.origin
        display 由接入方填写，将显示在用户的 HumanLink 设备上
        """

    def verify(
        self,
        assertion: dict,
        challenge: Challenge,
    ) -> VerifyResult:
        """
        10 步验证（本地和云端完全一致，chain_check 配置决定步骤 10 是否执行）：

        1.  结构校验        — type、必选字段完整
        2.  设备绑定        — assertion.device.id == challenge.requiredIssuerDID
        3.  actionHash     — 计算含 requiredIssuerDID 的 hash，与 challenge 比对
        4.  origin 绑定    — challenge.origin 与本端一致
        5.  nonce 防重放   — nonce 未使用过，使用后标记
        6.  时间窗口        — created 在 max_age_seconds 内
        7.  证据校验        — matchScore ≥ min_match_score
        8.  设备信任        — attestation 满足 trust_policy
        9.  签名校验        — 以 requiredIssuerDID 解析公钥验 ECDSA 签名
        10. 链上校验        — isValidIssuer(requiredIssuerDID) + isRevoked()
                             （chain_check=skip 时跳过）

        返回：
          VerifyResult(
            valid: bool,
            device_did: str,
            match_score: int,
            device_attestation: dict,
            failure_reason: Optional[str]
          )
        """
```

### 集成示例：云端流程（Agent 平台）

前提：平台必须维护用户绑定表，`userId` 由平台自身 Auth 层（IAM/Gateway 解析 Agent Token）可信传入，HumanLink 不处理 Agent 身份认证。

```
Agent Identity / Session Token
       ↓ 平台 Auth 层 / AI Gateway 解析
    userId
       ↓ 平台用户表 / 链上 UserDeviceRegistry
  requiredIssuerDID
       ↓
  Challenge 生成（含 requiredIssuerDID）
```

```python
# 云端 Agent 平台集成示例（以 Copilot 类平台为例）

verifier = HumanLinkVerifier(
    issuer_registry_address="0x...",
    user_device_registry_address="0x...",
    rpc_url="https://sepolia.infura.io/v3/...",
    origin="copilot.example.com",
    min_match_score=100
)

@app.post("/api/agent/transfer")
async def agent_transfer(req: AgentTransferRequest, session: UserSession):
    if req.amount > 100 or req.to not in session.user.trusted_list:

        challenge = verifier.create_challenge(
            user_id=session.user_id,
            action="transfer",
            action_params={"to": req.to, "amount": req.amount, "currency": "USD"},
            display_title="转账确认",
            display_summary=f"向 {req.to} 转账 ${req.amount}",
            risk="high"
        )

        assertion = await humanlink_client.request_auth(challenge)

        result = verifier.verify(assertion=assertion, challenge=challenge)

        if not result.valid:
            raise HTTPException(403, detail={
                "error": f"HumanLink: {result.failure_reason}",
                "step": result.failure_step
            })

        await audit_log.write(
            user_id=session.user_id,
            action="transfer",
            params=req.dict(),
            assertion_id=assertion["id"],
            device_did=result.device_did,
            timestamp=assertion["created"]
        )

    return execute_transfer(req)
```

### 集成示例：本地流程（OpenClaw）

```python
# 本地场景集成示例（OpenClaw approval_hook）

from humanlink_sdk import HumanLinkVerifier, HumanLinkClient

verifier = HumanLinkVerifier(
    config_path="~/.humanlink/config.yaml"   # 本地配置，无需链上参数
)
client = HumanLinkClient(transport="usb")

def humanlink_approval(command: str, context: dict) -> bool:
    challenge = verifier.create_challenge(
        action=context["tool"],
        action_params=context["params"],
        display_title="命令执行确认",
        display_summary=command[:100],
        risk=context.get("risk_level", "high"),
        origin="local://openclaw"
    )
    try:
        assertion = client.request_auth(challenge=challenge, timeout_seconds=30)
    except TimeoutError:
        return False

    result = verifier.verify(assertion=assertion, challenge=challenge)
    return result.valid
```

---

### HumanLink 本地设计：本地 Agent + AI Gateway 集成

> 针对 Agent 跑在用户自己机器上、无中心服务器的场景。
> 

### 场景定义

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

### 与 OpenClaw 的集成

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

### OpenClaw 集成实现

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

### 本地架构

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

### 本地验证模式

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

### 本地审计记录

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

### 设备初始化流程

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

### 安全边界说明

| 问题 | 本地场景的处理 |
| --- | --- |
| 设备被盗后仍能签名 | 链上 revokeIssuer() 有效；offline 时无法实时检查，建议定期联网同步吊销列表 |
| 本地配置文件被篡改 | requiredIssuerDID 被改 → 设备自验 DID 不一致 → 设备拒绝响应 |
| Agent 绕过 OpenClaw 直接调用系统 | OpenClaw 沙箱隔离职责，与 HumanLink 无关 |
| 审计记录被删除 | 本地记录可选同步到链上 AuditLog；删除记录本身可被发现（记录有序列号） |
| elevated: full 时跳过 HumanLink | 这是 OpenClaw 原有设计，HumanLink 尊重该配置，需用户显式设置 |

---

## 五、云端流程

### 协议设计 HumanLink Assertion Protocol v0.3

### Challenge 生成机制：Platform-Initiated Only

HumanLink 的 Challenge **只能由 Agent 平台生成**。Agent 不参与 Challenge 的生成、传递或修改。

```
Agent               Agent 平台（Copilot/Cursor/...）   HumanLink Issuer
  │                          │                              │
  │  1. API 调用              │                              │
  │  transfer(to, amount)    │                              │
  │ ────────────────────────▶│                              │
  │                          │                              │
  │                          │  2. 风险评估（平台决定）       │
  │                          │  金额 > 阈值？                │
  │                          │  → 需要 HumanLink 认证        │
  |                           │ 3. 查用户绑定设备 DID        │
  |                           │    UserDeviceRegistry       │
  |                           │    .getDeviceDID(userId)    │
  |                          │    → requiredIssuerDID       │
  │                          │  4. 生成 Challenge            │
  │                          │  origin = copilot.ai         │
  │                          │  requiredIssuerDID 嵌入       │
  │                          │  actionHash 含 DID           │
  │                          │  display = 平台填写           │
  │                          │ ────────────────────────────▶│
  │                          │                              │
      │                    │                5. 设备自验：
      │                    │                   自身 DID == requiredIssuerDID?
      │                    │                   否则拒绝响应
      │                    │                          │
      │                    │                6. 屏幕显示
      │                    │                   操作摘要
      │                    │                          │
      │                    │                7. 用户按指纹
      │                    │                   HAI.auth(h_doc)
      │                    │                 → signature by requiredIssuerDID
  │                          │                              │
  │                          │  8. 返回 Assertion            │
  │                          │ ◀────────────────────────────│
  │                          │                              │       链上
      │                    │ 9. 10 步验证                   │         │
      │                    │  [2] device.id                 │         │
      │                    │      ==requiredDID ✓           │         │
      │                    │  [3] actionHash ✓              │         │
      │                    │  [9] ECDSA ✓ ────────────────────────▶  │
      │                    │  [10] isValidIssuer ✓          │ ←───────│
  │                          │                              │
  │  10. 返回执行结果         │                              │
  │ ◀────────────────────────│                             │
```

**Agent 完全不接触 Challenge**。Agent 调用平台 API，平台自行决定是否需要认证、自行生成 Challenge、自行与 HumanLink Issuer 通信。Agent 只知道"操作成功"或"操作被拒绝"，不知道认证流程的存在，因此也无法绕过或伪造。

**`actionHash` 由平台基于真实 API 参数计算**。即使 Agent 描述的是"更新偏好"，但平台解析到的实际调用是 `deleteAccount(id=12345)`——Challenge 里写的是后者，用户屏幕上显示的也是后者。

**`display` 由平台填写**。用户在 HumanLink 设备上看到的操作摘要来自 Agent 平台，不来自 Agent 本身。平台对自己拦截到的业务语义的描述是可信的。

### 核心数据结构：HumanPresenceAssertion

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
    "actionHash": "sha256(transfer ‖ Alice ‖ 500 ‖ USD ‖ nonce ‖ did:key:z6MkBob...)",
    "nonce": "a1f3b7c-...",
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
    "sensorSerial": "A3B4C5D6..."
  },

  "proof": {
    "type": "ECDSA-P256",
    "signedHash": "sha256(matched_id ‖ score ‖ sensor_serial ‖ h_doc)",
    "signature": "3045022100...",
    "verificationMethod": "did:key:z6MkBob...#key-0"
  }
}
```

### 字段说明

**`device`**：签发设备的身份和资质。`id` 是由安全芯片公钥派生的 `did:key`，链上 IssuerRegistry 注册且必须与 `challenge.requiredIssuerDID` 完全一致。`attestation` 是设备自报的硬件能力，Verifier 据此实施分级信任——有安全芯片 + 活体检测的设备信任等级最高。

**`subject`**：本地匹配结果的最小声明。`localId` 是传感器内部的槽位标识（如 JM-101 的模板 ID），`isRegistered` 表示该槽位有已注册模板。协议层不涉及用户真实身份——"slot-03 = 张三"这个映射由应用层维护。

**`challenge`**：由请求方（Agent 平台）生成的一次性挑战。`actionHash` 将授权绑定到具体操作参数，防止签名被挪用到其他操作。`nonce` 防重放。`origin` 防跨域。`requiredIssuerDID` 绑定签发设备。

**`challenge.requiredIssuerDID`**：Challenge 里显式写明"必须由哪台设备签名"。Issuer 收到 Challenge 后，先校验 `requiredIssuerDID == self.get_device_did()`，不匹配则拒绝响应。

**`challenge.actionHash`**：hash 输入追加 `requiredIssuerDID`，使 actionHash 与特定设备不可分离。即使攻击者构造完全相同的操作参数，因 DID 不同，actionHash 仍无法通过。

**`proof.verificationMethod`**：必须与 `challenge.requiredIssuerDID` 一致，Verifier 以此为根取公钥做最终签名验证。

**`evidence`**：传感器匹配证据。`matchScore` 写入断言，Verifier 可设置最低置信度阈值。`sensorSerial` 是传感器芯片唯一序列号，建立传感器 ↔ 签名的硬件绑定。

**`proof`**：设备安全芯片的 ECDSA P-256 签名。签名输入 `H_final = SHA256(matched_id ‖ score ‖ sensor_serial ‖ H_doc)`，其中 `H_doc` 是 Assertion 骨架（不含 proof 字段）经 JSON-LD 规范化后的哈希。验证方用 `did:key` 解析出设备公钥进行验签。单签名结构，无嵌套。`verificationMethod` 必须指向 `requiredIssuerDID` 对应的公钥

### 链上验证层

```
不上链：                               必须上链（v0.3）：
──────────────────                     ──────────────────────────
· 生物特征数据                          · Device DID + pk_issuer
· 安全芯片私钥                            (IssuerRegistry)
· Assertion 原文                        · 用户账号 ↔ 设备 DID 绑定
· 传感器模板数据                          (UserDeviceRegistry 本地) 路径)
· 用户真实身份                          · 断言撤销状态
                                          (AssertionStatusRegistry)

                                        可选上链：
                                        ──────────────────────────
                                        · 高危操作审计摘要 (AuditLog)
```

### 合约接口

```solidity
// contracts/IssuerRegistry.sol

interface IIssuerRegistry {
    /// @notice 注册新设备，含硬件资质元数据
    function registerIssuer(
        bytes calldata pkIssuer,
        string calldata did,
        string calldata attestationHash
    ) external;

    /// @notice 查询设备是否有效
    function isValidIssuer(bytes calldata pkIssuer)
        external view returns (bool);

    /// @notice 吊销设备
    function revokeIssuer(bytes32 issuerHash) external;

    event IssuerRegistered(bytes32 indexed issuerHash, string did);
    event IssuerRevoked(bytes32 indexed issuerHash, uint256 timestamp);
}

// contracts/UserDeviceRegistry.sol  ← v0.3新增
/*
说明：云端平台内部数据库已维护 userId → deviceDID 映射时可不依赖此合约，直接从自有 DB 取。UserDeviceRegistry 主要为本地（个人用户）场景提供链上标准查询接口。
*/
interface IUserDeviceRegistry {
    /// @notice 本地: 用户自主绑定设备 DID 到自己的账号
    function bindDevice(
        bytes32 userIdHash,       // keccak256(userId)，隐私保护
        string calldata deviceDID
    ) external;

    /// @notice 查询用户绑定的设备 DID
    function getDeviceDID(bytes32 userIdHash)
        external view returns (string memory);

    /// @notice 用户解绑（更换设备时使用）
    function unbindDevice(bytes32 userIdHash) external;

    event DeviceBound(bytes32 indexed userIdHash, string deviceDID);
    event DeviceUnbound(bytes32 indexed userIdHash, uint256 timestamp);
}

// contracts/AssertionStatusRegistry.sol

interface IAssertionStatusRegistry {
    function revokeAssertion(bytes32 assertionHash) external;

    function isRevoked(bytes32 assertionHash)
        external view returns (bool);

    event AssertionRevoked(bytes32 indexed assertionHash, uint256 timestamp);
}
```

### 生命周期

```
阶段一：部署（一次性）
────────────────────────────────────
部署 IssuerRegistry、UserDeviceRegistry、AssertionStatusRegistry 到 Sepolia

阶段二：设备注册（每台设备一次）
────────────────────────────────────
管理员调用 IssuerRegistry.registerIssuer(pk, did, attestationHash)
设备加入可信 Issuer 网络

阶段三：运行时
────────────────────────────────────
签发：Issuer 在 Assertion 中写入 device.id（== requiredIssuerDID）
验证：Verifier 10 步校验，含链上 isValidIssuer()
撤销：revokeAssertion() 撤销特定断言

阶段四：设备损坏/被盗
────────────────────────────────────
管理员调用 revokeIssuer(issuerHash)
→ 该设备所有新断言验证失败（Step 10 返回 false）
```

### 协议约束和扩展点

| 约束 | 规则 |
| --- | --- |
| 单次有效 | 每份 Assertion 绑定唯一 nonce，用后即弃 |
| 设备绑定 | requiredIssuerDID 锁定签发设备，防设备替换攻击 |
| 操作绑定 | actionHash 含设备 DID + 操作参数，双重绑定 |
| 域名绑定 | origin 限定请求来源，防跨域重放 |
| 时间窗口 | Verifier 检查 created 与当前时间差，建议上限 30 秒 |
| 不可缓存 | 无 TTL，不支持断言复用 |
| 置信度门槛 | Verifier 可设 matchScore 最低阈值 |
| 平台主权 | Challenge 由承担责任的一方生成，Agent 无权接触 |
| 显示真实性 | 用户看到的操作摘要来自平台，不来自 Agent |

| 扩展 | 说明 | 启用条件 |
| --- | --- | --- |
| `holderProof` | 可选第二层用户身份签名 | HAI 实现支持独立用户密钥管理时 |
| `subject.did` | 可选用户 DID 声明 | 应用场景需要跨设备身份连续性时 |
| `evidence.livenessScore` | 活体检测置信度 | 传感器支持活体检测时 |

### 面向 OEM：硬件抽象接口 (HAI)

任何想成为 HumanLink Issuer 的设备必须实现此接口。当前参考实现是其中之一；未来手机 TEE、工控机、POS 机都可以是合规实现。

```python
class HumanLinkIssuer(Protocol):
    """
    硬件抽象接口定义
    """

    def get_device_did(self) -> str:
        """
        返回设备 DID (did:key)。
        公钥来源于设备安全芯片，私钥永不出芯片。
        """

    def get_attestation(self) -> Attestation:
        """
        返回设备硬件资质，用于 IssuerRegistry 注册和 Verifier 信任分级。

        Attestation:
          sensor_type: str      # "optical_fingerprint" / "iris" / "face_3d" ...
          sensor_far: float     # False Accept Rate
          sensor_frr: float     # False Reject Rate
          secure_element: str   # "ATECC608A" / "TPM2.0" / "Apple_SE" ...
          liveness: bool        # 是否支持活体检测
        """

    def authenticate(self, h_doc: bytes) -> AuthResult:
        """
        核心方法：验证请求方要求的设备 DID 与自身一致，再触发生物认证。

        输入：
          h_doc        — Assertion 骨架规范化哈希
          required_did — Challenge 中的 requiredIssuerDID

        内部流程：
          0. 验证 required_did == self.get_device_did()，不一致立即拒绝
          1. 触发生物特征采集
          2. 本地模板匹配 → matched_id + score
          3. H_final = SHA256(matched_id ‖ score ‖ sensor_serial ‖ h_doc)
          4. signature = secure_element.sign(H_final)
          5. 清除所有生物特征数据

        AuthResult:
          matched_id: int       # 匹配的本地模板槽位
          score: int            # 匹配置信度分值
          sensor_serial: str    # 传感器芯片唯一序列号
          signature: bytes      # 安全芯片 ECDSA 签名
        """
```

协议不关心传感器类型、不关心安全芯片型号——只要求设备能输出 **"匹配成功 + 硬件签名"**。

未来 HAI 实现（如手机 Secure Enclave）可按需启用，向后兼容。

| 扩展 | 说明 | 启用条件 |
| --- | --- | --- |
| `holderProof` | 可选的第二层用户身份签名 | HAI 实现支持独立用户密钥管理时 |
| `subject.did` | 可选的用户 DID 声明 | 应用场景需要跨设备身份连续性时 |
| `evidence.livenessScore` | 活体检测置信度 | 传感器支持活体检测时 |

---

## Demo 实现架构

> ESP32 U盾（ESP32-WROOM + JM-101 + ATECC608A）是 HumanLink 协议的第一个 HAI 实现实例。U盾通过 USB Serial 插入 PC，PC 运行 HumanLink SDK 守护进程——协议端到端跑通。
> 

### 文件总结构

```
humanlink/
├── protocol/                          ← 协议规范（唯一权威来源）
│   ├── assertion_spec.md              ← HumanPresenceAssertion 格式规范
│   ├── hai_spec.md                    ← 硬件抽象接口 (HAI) 规范
│   ├── verification_spec.md           ← 10 步验证流程规范
│   ├── SDK↔Firmware.md            ← actionHash/signedHash 构造 + USB Serial 接口契约
│   └── SDK↔AI Gateway.md          ← OpenClaw approval_hook ↔ PC SDK 接口契约
│
├── sdk/                               ← HumanLink SDK（守护进程 + 验证器）
│   ├── verifier.py                    ← HumanLinkVerifier（chain_check 配置决定是否上链）
│   ├── client.py                      ← USB Serial Issuer 客户端
│   ├── trust_policy.py                ← 设备信任策略
│   ├── device_registry.py             ← 用户-设备绑定管理
│   ├── types.py                       ← 类型定义
│   ├── hardware/
│   │   ├── usb_bridge.py              ← USB Serial 通信
│   │   └── protocol.py                ← 数据帧协议
│   ├── assertion/
│   │   ├── builder.py                 ← 组装 + 规范化 + 注入
│   │   └── schema.py                  ← 结构校验
│   ├── identity/
│   │   ├── issuer_did.py              ← 设备 DID
│   │   └── did_resolver.py            ← DID 解析
│   ├── crypto/
│   │   ├── ecdsa_verify.py            ← 签名验证
│   │   └── hash_engine.py             ← JSON-LD 规范化 + H_doc
│   ├── chain/
│   │   ├── issuer_registry.py         ← 合约调用
│   │   ├── user_device_registry.py    ← 用户设备注册
│   │   └── assertion_status.py        ← 撤销管理
│   ├── api/
│   │   ├── server.py                  ← FastAPI 守护进程入口
│   │   ├── routes.py                  ← 路由
│   │   └── ws_client.py               ← 云端流程：WebSocket 接收云端 Challenge
│   └── db/
│       └── store.py                   ← SQLite
│
├── firmware/                          ← ESP32 固件 (C++)
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp                   ← 主循环
│       ├── jm101.cpp / .h             ← JM-101 驱动
│       ├── atecc608a.cpp / .h         ← ATECC608A I2C 封装
│       └── protocol.h                 ← 协议常量与结构体
│
├── contracts/                         ← 链上合约
│   ├── IssuerRegistry.sol
│   ├── UserDeviceRegistry.sol         ← 用户账号↔设备DID绑定
│   ├── AssertionStatusRegistry.sol
│   ├── hardhat.config.js
│   └── scripts/deploy.js
│
├── apps/
│   └── openclaw/                      ← OpenClaw approval_hook Demo
│
├── config.yaml
├── requirements.txt
└── README.md
```

```yaml
# config.yaml 参考实现配置

# config.yaml

hardware:
  sensor: "jm101"
  sensor_baud: 57600
  controller: "esp32"
  secure_element: "atecc608a"
  se_slot: 0
  transport: "usb_serial"
  serial_port: "/dev/ttyUSB0" # Linux/Windows 用 "COM3"；Mac 用 "/dev/tty.usbserial-*"
  usb_baud: 115200

protocol:
  version: "0.3"
  context_local: "/etc/humanlink/context-v1.jsonld"

chain:
  network: "sepolia"
  rpc_url: "https://sepolia.infura.io/v3/_KEY"
  issuer_registry: "0x..."
  user_device_registry: "0x..."
  assertion_status: "0x..."

verification:
	chain_check: "required"    # 云端: required；本地: optional / skip
  max_age_seconds: 30
  min_match_score: 100
  trust_policy: "default"             # default / strict / custom
  enforce_device_binding: true        # 开启设备绑定

# 云端场景：WebSocket 接收云端 Challenge
gateway:
  mode: "websocket"                   # websocket（云端）| local（本地）
  ws_url: "wss://platform.example.com/humanlink/ws"
  token: "YOUR_DEVICE_TOKEN"
  
api:
  host: "127.0.0.1"
  port: 8765
```

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
ESP32-WROOM-32          JM-101                ATECC608A
──────────────          ──────                ─────────
TX0 (GPIO1) ─────────── RX (Pin3)
RX0 (GPIO3) ─────────── TX (Pin2)
3.3V ───────────────── VCC (Pin1)
GND ────────────────── GND (Pin4)
GPIO4 ─────────────── Touch (Pin5, 可选中断唤醒)
3.3V ──────────────── TouchVin (Pin6)
GPIO21 (SDA) ──────────────────────────────── SDA
GPIO22 (SCL) ──────────────────────────────── SCL
3.3V ────────────────────────────────────── VCC
GND ─────────────────────────────────────── GND

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

## 附 安全创新卖点

### 核心创新点

1. **单次按压 = 单次断言**：将传统"签发凭证 → 出示凭证"两步流程压缩为一次物理按压，无中间态可攻击。
2. **硬件签名直接构成断言证明**：省去中间 VC 层，减少攻击面和数据流转环节。
3. **操作原子绑定**：Challenge 绑定具体操作参数（actionHash），实现授权与操作的原子绑定，防止授权调包。
4. **Challenge 不经 Agent**：Challenge 由承担责任的一方生成，Agent 全程不接触，无法伪造或旁路。
5. **设备绑定**：Challenge 嵌入 `requiredIssuerDID`，actionHash 含设备 DID，从根本上堵死设备替换攻击路径。
6. **三重设备校验**：`device.id`（Assertion 结构）、`verificationMethod`（签名验证）、`isValidIssuer`（链上）均以 `requiredIssuerDID` 为基准，三处全部校验

| 安全属性 | 实现机制 | 组件 |
| --- | --- | --- |
| 生物数据不出传感器模块 | JM-101 模块内完成比对 | JM-101 |
| 私钥永不出芯片 | ATECC608A Slot 0 不可读 | ATECC608A |
| 防重放 | H_doc 含 nonce，每次唯一 | 协议层 |
| 防操作调包 | actionHash 绑定全部操作参数 | 协议层 |
| 防跨域挪用 | origin 绑定来源 | Verifier SDK |
| 防延迟攻击 | created 时间窗口（30 秒） | Verifier SDK |
| 防设备替换攻击 | requiredIssuerDID 嵌入 Challenge + actionHash | 协议层 |
| 设备三重校验 | device.id / verificationMethod / isValidIssuer 均对齐 requiredIssuerDID | 协议层 + 链上 |
| Agent 无法伪造 | Challenge 由平台生成，Agent 不接触 | 架构设计 |
| 设备可溯源 | pk_issuer → did:key → IssuerRegistry | 链上 |
| 设备可吊销 | revokeIssuer() → 整批失效 | 链上 |
| 断言可撤销 | revokeAssertion() | 链上 |
| 匹配置信度可审计 | matchScore 写入 Assertion | 协议层 |
| 设备信任分级 | attestation + trust_policy | HumanLink SDK |
| 可举证（云端） | 审计库 + 链上，平台无需 HumanLink 配合即可举证 | 平台层 |
| 可举证（本地） | 本地审计记录由设备私钥签名。链上 UserDeviceRegistry，用户可自证 | 本地 + 链上 |

---

*文档版本 v2.2 | HumanLink Protocol v0.3*

Q/A: 

1. 为什么使用设备绑定DID？——初版协议只解决设备合法性（注册或注销拥有授权权限的设备），至于设备由多少个人管理，是由硬件是否支持活体检测比对决定的。人负责掌控对设备的控制权以及责任本地归属上的变动。
2. Agent发起请求的时候如何知道自己绑定的哪个用户？—— HumanLink 不处理 Agent 身份认证，这是 IAM/Gateway 层的职责，`userId` 必须由上游可信地传入。关键在于 Agent 调用平台 API 时，必须携带凭证（session token / API key / OAuth token），这个凭证在颁发时就已经绑定了用户身份。