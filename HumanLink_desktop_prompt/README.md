# HumanLink Desktop Prompt

独立桌面提示程序（PySide6），用于展示 HumanLink 认证流程关键步骤。

## 特性

- 独立进程运行，不修改现有 SDK / 前端 / 后端 / 设备端代码
- 本地 HTTP 接口 `POST /track` 接收会话 `session_id`
- 实时轮询 SDK `GET /auth/status/{session_id}` 显示进度
- 托盘常驻 + 自动弹窗 + 历史记录

## 快速启动

```powershell
cd HumanLink_desktop_prompt
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

默认配置：

- 桌面提示服务：`http://127.0.0.1:8989`
- SDK 地址：`http://127.0.0.1:8765`
- 轮询间隔：`500ms`
- 单会话超时：`45s`

## 接口

### POST /track

Request:

```json
{
  "session_id": "b485f5cf-2f2c-4c90-8b2b-f5377fd2f17f",
  "risk_level": "high",
  "display_title": "高危命令授权",
  "display_summary": "rm -rf /important"
}
```

Response:

```json
{
  "accepted": true,
  "session_id": "b485f5cf-2f2c-4c90-8b2b-f5377fd2f17f",
  "tracking_id": "a10f7a8bce9f46f4a8f8473ac4190f7e"
}
```

重复 `session_id` 会幂等返回同一个 `tracking_id`。

## 运行参数

```powershell
python app.py --listen-port 8989 --sdk-base-url http://127.0.0.1:8765 --poll-interval-ms 500 --session-timeout-seconds 45
```

## 测试

```powershell
pytest -q
```

## 联调演示用例（推荐先跑这个）

下面用 Mock SDK 演示桌面弹窗效果，不依赖真实设备。

### 1) 启动 Mock SDK（终端A）

```powershell
cd HumanLink_desktop_prompt
python tools\mock_sdk_server.py --port 18765
```

### 2) 启动桌面提示程序（终端B）

```powershell
cd HumanLink_desktop_prompt
python app.py --sdk-base-url http://127.0.0.1:18765 --listen-port 8989 --session-timeout-seconds 6
```

### 3) 发起测试会话（终端C）

先创建一个 mock session（成功场景）：

```powershell
$body = @{ scenario = "success" } | ConvertTo-Json
$session = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18765/mock/create" -ContentType "application/json" -Body $body
$session
```

把 `session_id` 交给桌面提示程序：

```powershell
$track = @{
  session_id = $session.session_id
  risk_level = "high"
  display_title = "高危命令授权"
  display_summary = "rm -rf /important"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8989/track" -ContentType "application/json" -Body $track
```

预期弹窗顺序：
1. 检测到高危操作
2. 正在发起认证 / challenge 已生成
3. 正在连接设备
4. 请按压拇指进行授权
5. 已采集指纹，正在校验签名
6. 认证成功

### 4) 失败与超时场景

- 失败：把 `scenario` 改为 `failed`
- 超时：把 `scenario` 改为 `timeout`（桌面程序会在 `--session-timeout-seconds` 到达后显示认证超时）

### 5) 幂等用例（重复 session）

对同一个 `session_id` 连续调用两次 `/track`，返回的 `tracking_id` 应相同。

## 一键演示脚本

```powershell
cd HumanLink_desktop_prompt
powershell -ExecutionPolicy Bypass -File .\tools\run_demo.ps1
```

脚本会自动：
1. 启动 Mock SDK
2. 启动桌面提示程序
3. 依次触发 `success` / `failed` / `timeout` 三个场景
4. 等你按 Enter 后自动停止进程
