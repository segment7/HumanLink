# HumanLink SDK 本地演示指南

> 本指南面向 Demo 评委，从零开始本地跑通 HumanLink 生物识别授权全流程。

---

## 系统要求


| 项目     | 要求                      |
| ------ | ----------------------- |
| Python | 3.9+                    |
| OS     | macOS / Linux / Windows |
| HumanLink设备   | 可选（无设备可使用模拟模式）          |


---

## 环境准备

```bash
cd sdk/
python -m venv .venv
source .venv/bin/activate        # Windows: source venv/Scripts/activate
pip install -r requirements.txt
```

## 一键演示（推荐）

```bash
python cli.py demo
```

此命令自动启动三个组件并发送模拟审批事件：

```
┌─────────────────────────────────────────────────────────┐
│  Mock Gateway (ws://127.0.0.1:18789)                    │
│       ↓  exec.approval.requested                        │
│  Bridge (WebSocket client)                              │
│       ↓  POST /auth/challenge + /auth/execute           │
│  SDK Daemon (http://127.0.0.1:8765)                     │
│       ↓  USB 通信                                       │
│  HumanLink 设备 (指纹采集 + ECDSA 签名)                       │
│       ↑  assertion 返回                                  │
│  SDK Daemon → 10步验证                                   │
│       ↑  allow-once / deny                               │
│  Bridge → Gateway (exec.approval.resolve)               │
└─────────────────────────────────────────────────────────┘
```

### 预期终端输出

```
╭─────────────────────────────────────────────────────────╮
│ HumanLink Demo Mode                                     │
│ 一键演示: Mock Gateway → Bridge → SDK → HumanLink             │
╰─────────────────────────────────────────────────────────╯
  Mock Gateway          ws://127.0.0.1:18789
  SDK Daemon            http://127.0.0.1:8765
  Device Mode           USB HumanLink

✓ SDK daemon starting...
✓ Mock Gateway starting on ws://127.0.0.1:18789
✓ Bridge connecting to Mock Gateway...

All components running.

╭─────────────────────────────────────────────────────────╮
│ Sending 3 simulated exec.approval.requested events      │
│ Each event triggers the full: Gateway → Bridge → SDK →  │
│ HumanLink flow                                                │
╰─────────────────────────────────────────────────────────╯

━━━ Demo [1/3] ━━━
Agent requests to delete critical user data

╭──────────── HumanLink Authorization ────────────────────╮
│                                                          │
│   Action    rm -rf /home/user/important_data             │
│   Risk      ██████████ HIGH                              │
│   Agent     claude-code-agent                            │
│                                                          │
╰──────────────────────────────────────────────────────────╯
╭──────────────────────────────────────────────────────────╮
│              ▶ 请触碰 HumanLink确认...                          │
╰──────────────────────────────────────────────────────────╯
```

### 有 HumanLink 时（认证成功）

用户触碰设备后，显示 10 步验证进度：

```
 [1/10]    结构验证 — 检查断言格式        ✓
 [2/10]    设备绑定 — 验证设备 DID        ✓
 [3/10]    动作哈希 — 校验操作完整性      ✓
 [4/10]    源绑定 — 验证请求来源          ✓
 [5/10]    防重放 — 检查 nonce 唯一性     ✓
 [6/10]    时间窗口 — 校验时效性          ✓
 [7/10]    匹配分数 — 生物识别质量        ✓
 [8/10]    设备信任 — 验证设备可信度      ✓
 [9/10]    ECDSA 签名 — 数字签名验证      ✓
 [10/10]   链上校验 — 证书链验证          ✓

╭──────────────────────────────────────────────────────────╮
│  授权成功                                                 │
│                                                          │
│  Assertion: urn:uuid:550e8400-e29b-41d4-a716-...         │
│  Device:    did:key:z6MkBob...                           │
│  Score:     188                                          │
╰──────────────────────────────────────────────────────────╯

Gateway received resolution: allow-once
```

### 无 HumanLink 时（预期超时）

SDK daemon 启动时无法连接设备，`auth/execute` 返回 503：

```
Gateway received resolution: deny
```

这表明安全策略生效：无物理设备 = 无法授权。

---

## API 直接调用（高级）
### 守护程序启动指南
```
cd sdk && python -m venv venv  
mac:source venv/bin/activate  
win: source venv/Scripts/activate   
pip install -r requirements.txt  
python run_server.py
```

守护程序 运行时，可直接调用 REST API：

```bash
# 健康检查
curl http://127.0.0.1:8765/health

# 预期：
# {"status":"healthy","timestamp":"...","device_connected":true}

# 创建认证挑战
curl -X POST http://127.0.0.1:8765/auth/challenge \
  -H "Content-Type: application/json" \
  -d '{
    "action": "exec",
    "action_params": {"command": "rm -rf /"},
    "display_title": "命令执行确认",
    "display_summary": "rm -rf /",
    "risk": "high",
    "origin": "local://demo",
    "user_id": "demo_user"
  }'

# 预期：
# {"challenge":{...},"session_id":"uuid-here"}

# 查看 API 文档
open http://127.0.0.1:8765/docs
```

---

## 架构说明

```
                    ┌──────────────────────────┐
                    │   AI Agent (Claude等)     │
                    │   执行高风险操作           │
                    └──────────┬───────────────┘
                               │
                    ┌──────────▼───────────────┐
                    │   AI Gateway (OpenClaw)   │
                    │   exec.approval 策略引擎  │
                    │   ws://gateway:18789      │
                    └──────────┬───────────────┘
                               │ WebSocket
                               │ exec.approval.requested
                    ┌──────────▼───────────────┐
                    │   HumanLink Bridge        │
                    │   协议转换 + 事件路由      │
                    └──────────┬───────────────┘
                               │ HTTP REST
                               │ /auth/challenge → /auth/execute
                    ┌──────────▼───────────────┐
                    │   HumanLink SDK Daemon    │
                    │   http://localhost:8765   │
                    │   认证会话管理 + 10步验证  │
                    └──────────┬───────────────┘
                               │ USB Serial
                    ┌──────────▼───────────────┐
                    │   HumanLink HumanLink 硬件      │
                    │   指纹采集 → ECDSA签名    │
                    │   安全芯片 ATECC608A      │
                    └──────────────────────────┘
```

**核心安全设计：**

- Gateway 代码：零修改（标准 OpenClaw exec approval 机制）
- SDK 代码：零修改（标准 HumanLink 认证 API）
- Bridge 仅做协议转换，不持有密钥、不做风险决策
- 私钥永不离开 HumanLink 安全芯片
- 每次授权产生不可伪造的 ECDSA 签名断言

---

## 文件结构

```
sdk/
├── cli.py                      # CLI 入口 (humanlink 命令)
├── run_server.py               # SDK server 独立启动 (已被 cli.py 取代)
├── requirements.txt            # Python 依赖
├── api/
│   └── server.py               # FastAPI daemon (localhost:8765)
├── bridge/
│   ├── __init__.py
│   ├── gateway_bridge.py       # Gateway ↔ SDK 桥接
│   ├── mock_gateway.py         # 模拟 Gateway (demo 用)
│   ├── tui.py                  # Rich TUI 终端界面
│   └── notifier.py             # OS 原生通知
├── client.py                   # USB 设备通信
├── verifier.py                 # 10步验证引擎
└── data_types.py               # 数据类型定义
```

