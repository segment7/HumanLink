#!/usr/bin/env python
"""
HumanLink CLI

Usage:
    humanlink daemon run      — run daemon in foreground (TUI mode)
    humanlink daemon start    — start daemon in background
    humanlink daemon stop     — stop background daemon
    humanlink status          — show device and daemon status
    humanlink auth test       — trigger a test authentication flow
"""
import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add sdk root to path
SDK_ROOT = Path(__file__).parent
sys.path.insert(0, str(SDK_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

console = Console()

# PID file for daemon management
PID_FILE = Path.home() / ".humanlink" / "daemon.pid"


def main():
    parser = argparse.ArgumentParser(
        prog="humanlink",
        description="HumanLink — Agent 人类授权基础设施",
    )
    sub = parser.add_subparsers(dest="command")

    # daemon
    daemon_parser = sub.add_parser("daemon", help="管理 HumanLink 守护进程")
    daemon_sub = daemon_parser.add_subparsers(dest="daemon_action")
    run_parser = daemon_sub.add_parser("run", help="前台运行（TUI 模式）")
    run_parser.add_argument("--gateway-url", default="ws://127.0.0.1:18789", help="Gateway WebSocket URL")
    run_parser.add_argument("--gateway-token", default="", help="Gateway auth token")
    run_parser.add_argument("--sdk-url", default="http://127.0.0.1:8765", help="SDK daemon URL")
    run_parser.add_argument("--sdk-only", action="store_true", help="只启动 SDK，不连接 Gateway")
    daemon_sub.add_parser("start", help="后台启动")
    daemon_sub.add_parser("stop", help="停止后台守护进程")

    # status
    sub.add_parser("status", help="显示设备和守护进程状态")

    # demo
    demo_parser = sub.add_parser("demo", help="一键演示完整 Gateway→Bridge→SDK 流程")
    demo_parser.add_argument("--port", type=int, default=18789, help="Mock Gateway 端口")
    demo_parser.add_argument("--sdk-port", type=int, default=8765, help="SDK daemon 端口")
    demo_parser.add_argument("--cmd", default="", help="自定义模拟命令（留空使用预设）")
    demo_parser.add_argument("--no-device", action="store_true", help="无 U盾 模式（跳过设备连接）")

    # auth
    auth_parser = sub.add_parser("auth", help="认证操作")
    auth_sub = auth_parser.add_subparsers(dest="auth_action")
    test_parser = auth_sub.add_parser("test", help="测试认证流程")
    test_parser.add_argument("--cmd", default="rm -rf /important", help="模拟的命令")
    test_parser.add_argument("--sdk-url", default="http://127.0.0.1:8765", help="SDK daemon URL")

    args = parser.parse_args()

    if args.command == "daemon":
        handle_daemon(args)
    elif args.command == "status":
        handle_status(args)
    elif args.command == "demo":
        handle_demo(args)
    elif args.command == "auth":
        handle_auth(args)
    else:
        parser.print_help()


# ---------------------------------------------------------------------------
# daemon
# ---------------------------------------------------------------------------

def handle_daemon(args):
    if args.daemon_action == "run":
        daemon_run(args)
    elif args.daemon_action == "start":
        daemon_start(args)
    elif args.daemon_action == "stop":
        daemon_stop()
    else:
        console.print("[yellow]Usage: humanlink daemon [run|start|stop][/]")


def daemon_run(args):
    """Run daemon in foreground with TUI."""
    from bridge.tui import render_auth_request, render_waiting_fingerprint, \
        render_verification_progress, render_result
    from bridge.notifier import notify

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    # Banner
    console.print()
    console.print(Panel(
        "[bold cyan]HumanLink Daemon[/]\n"
        "[dim]Agent 人类授权基础设施 — 守护进程[/]",
        border_style="cyan",
    ))

    # Show config
    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("key", style="dim", width=16)
    config_table.add_column("value")
    config_table.add_row("SDK URL", args.sdk_url)
    if not args.sdk_only:
        config_table.add_row("Gateway URL", args.gateway_url)
    config_table.add_row("Mode", "SDK only" if args.sdk_only else "SDK + Gateway Bridge")
    console.print(config_table)
    console.print()

    # Start SDK server + optional bridge
    asyncio.run(_run_daemon(args))


async def _run_daemon(args):
    """Run the combined SDK server + Gateway bridge."""
    import uvicorn

    tasks = []

    # 1. Start SDK API server
    config = uvicorn.Config(
        "api.server:app",
        host="127.0.0.1",
        port=8765,
        log_level="info",
    )
    server = uvicorn.Server(config)
    tasks.append(asyncio.create_task(server.serve()))

    console.print("[green]✓[/] SDK API server starting on http://127.0.0.1:8765")

    # 2. Optionally start Gateway bridge
    if not args.sdk_only:
        from bridge.gateway_bridge import HumanLinkBridge, GatewayConfig, SdkConfig

        bridge = HumanLinkBridge(
            gateway=GatewayConfig(
                url=args.gateway_url,
                token=args.gateway_token,
            ),
            sdk=SdkConfig(url=args.sdk_url),
            on_auth_request=_on_auth_request,
            on_auth_result=_on_auth_result,
        )
        tasks.append(asyncio.create_task(bridge.start()))
        console.print(f"[green]✓[/] Gateway bridge connecting to {args.gateway_url}")

    console.print()
    console.print("[bold green]Daemon running.[/] Press Ctrl+C to stop.")
    console.print("[dim]Waiting for exec.approval events...[/]")
    console.print()

    # Wait for all tasks
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


def _on_auth_request(command: str, agent_id: str, approval_id: str):
    """TUI callback when auth request arrives."""
    from bridge.tui import render_auth_request, render_waiting_fingerprint
    console.print(render_auth_request(command, "high", agent_id))
    console.print(render_waiting_fingerprint())


def _on_auth_result(approval_id: str, decision: str):
    """TUI callback when auth completes."""
    from bridge.tui import render_result
    success = decision == "allow-once"
    console.print(render_result(success, assertion_id=approval_id))
    console.print()


def daemon_start(args):
    """Start daemon in background."""
    console.print("[yellow]Background daemon not yet implemented. Use 'humanlink daemon run'.[/]")


def daemon_stop():
    """Stop background daemon."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            console.print(f"[green]Daemon (PID {pid}) stopped.[/]")
            PID_FILE.unlink()
        except ProcessLookupError:
            console.print("[yellow]Daemon not running. Cleaning up PID file.[/]")
            PID_FILE.unlink()
    else:
        console.print("[yellow]No daemon PID file found.[/]")


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------

def handle_demo(args):
    """One-click full demo: Mock Gateway + SDK + Bridge."""
    from bridge.tui import render_auth_request, render_waiting_fingerprint, \
        render_verification_progress, render_result
    from bridge.notifier import notify

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    sdk_port = args.sdk_port
    gw_port = args.port
    sdk_url = f"http://127.0.0.1:{sdk_port}"
    gw_url = f"ws://127.0.0.1:{gw_port}"

    # Banner
    console.print()
    console.print(Panel(
        "[bold cyan]HumanLink Demo Mode[/]\n"
        "[dim]一键演示: Mock Gateway → Bridge → SDK → U盾[/]",
        border_style="cyan",
    ))

    config_table = Table(show_header=False, box=None, padding=(0, 2))
    config_table.add_column("key", style="dim", width=20)
    config_table.add_column("value")
    config_table.add_row("Mock Gateway", f"ws://127.0.0.1:{gw_port}")
    config_table.add_row("SDK Daemon", f"http://127.0.0.1:{sdk_port}")
    config_table.add_row("Device Mode", "No-device (模拟)" if args.no_device else "USB U盾")
    console.print(config_table)
    console.print()

    # Pre-check: kill stale processes on target ports
    _kill_port_holders([sdk_port, gw_port])

    asyncio.run(_run_demo(args, sdk_url, gw_url, sdk_port, gw_port))


def _kill_port_holders(ports: list):
    """Detect and kill processes occupying the given ports."""
    import subprocess
    killed_any = False
    for port in ports:
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True, timeout=5,
            )
            pids = [p for p in result.stdout.strip().split() if p]
            if pids:
                console.print(f"[yellow]Port {port} occupied by PID {', '.join(pids)} — killing...[/]")
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGKILL)
                    except (ProcessLookupError, ValueError):
                        pass
                killed_any = True
        except Exception:
            pass
    if killed_any:
        time.sleep(1.5)
        console.print("[green]✓[/] Stale processes cleaned up.")


async def _run_demo(args, sdk_url, gw_url, sdk_port, gw_port):
    """Run the full demo flow."""
    import uvicorn
    from bridge.mock_gateway import MockGateway, DEMO_COMMANDS
    from bridge.gateway_bridge import HumanLinkBridge, GatewayConfig, SdkConfig
    from bridge.tui import render_auth_request, render_waiting_fingerprint, \
        render_verification_progress, render_result

    tasks = []

    # 1. Start SDK API server
    config = uvicorn.Config(
        "api.server:app",
        host="127.0.0.1",
        port=sdk_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    tasks.append(asyncio.create_task(server.serve()))
    console.print("[green]✓[/] SDK daemon starting...")

    # 2. Start Mock Gateway
    mock_gw = MockGateway(host="127.0.0.1", port=gw_port)
    tasks.append(asyncio.create_task(mock_gw.start()))
    console.print(f"[green]✓[/] Mock Gateway starting on ws://127.0.0.1:{gw_port}")

    # Give servers a moment to bind
    await asyncio.sleep(1.5)

    # 3. Start Bridge (connects to Mock Gateway, calls SDK)
    bridge = HumanLinkBridge(
        gateway=GatewayConfig(url=gw_url, token="demo-token"),
        sdk=SdkConfig(url=sdk_url),
        on_auth_request=_on_auth_request,
        on_auth_result=_on_auth_result,
    )
    tasks.append(asyncio.create_task(bridge.start()))
    console.print("[green]✓[/] Bridge connecting to Mock Gateway...")

    # Wait for bridge to connect
    await asyncio.sleep(2)

    console.print()
    console.print("[bold green]All components running.[/]")
    console.print()

    # 4. Wait for device connection before sending approval
    console.print("[cyan]Waiting for U盾 device...[/]")
    console.print("[dim]Please insert your HumanLink USB device. (timeout: 120s)[/]")
    console.print()

    import aiohttp
    device_ready = False
    device_deadline = time.time() + 120
    while time.time() < device_deadline:
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(f"{sdk_url}/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("device_connected"):
                            device_ready = True
                            console.print("[green]✓[/] U盾 device connected!")
                            console.print()
                            break
        except Exception:
            pass
        await asyncio.sleep(2)

    if device_ready:
        # Trigger device registration via /device/status
        try:
            async with aiohttp.ClientSession() as http:
                async with http.get(f"{sdk_url}/device/status", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        ds = await resp.json()
                        did = ds.get("device_did", "")
                        if did:
                            console.print(f"[dim]Device DID: {did}[/]")
        except Exception:
            pass
        console.print()
    else:
        console.print("[yellow]No device detected after 120s. Sending approval anyway (will result in deny).[/]")
        console.print()

    # 5. Fire one demo approval event
    demo = DEMO_COMMANDS[0]
    if args.cmd:
        demo = {"command": args.cmd, "risk": "high",
                "agent": "cli-user", "desc": "Custom command"}

    console.print(Panel(
        "[bold]Sending exec.approval.requested event[/]\n"
        "[dim]Gateway → Bridge → SDK → U盾 full flow[/]",
        border_style="yellow",
    ))
    console.print()

    approval_id = await mock_gw.send_approval_request(
        command=demo["command"],
        risk=demo["risk"],
        agent_id=demo["agent"],
    )

    if not approval_id:
        console.print("[red]No bridge connected.[/]")
    else:
        # Wait for resolution
        deadline = time.time() + 120
        while time.time() < deadline:
            result = mock_gw.get_result(approval_id)
            if result:
                console.print(f"[bold]Gateway received resolution: [{'green' if result == 'allow-once' else 'red'}]{result}[/][/]")
                console.print()
                break
            await asyncio.sleep(0.3)
        else:
            console.print("[yellow]Timeout — no resolution received.[/]")
            console.print()

    # Done
    console.print(Panel(
        "[bold green]Demo complete![/]\n"
        "[dim]Press Ctrl+C to exit[/]",
        border_style="green",
    ))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def handle_status(args):
    """Show device and daemon status."""
    import requests

    console.print()
    console.print(Panel("[bold]HumanLink Status[/]", border_style="cyan"))

    # Check SDK daemon
    sdk_url = "http://127.0.0.1:8765"
    try:
        resp = requests.get(f"{sdk_url}/health", timeout=30)
        data = resp.json()
        sdk_status = "[green]● Running[/]"
        device_connected = data.get("device_connected", False)
    except Exception:
        sdk_status = "[red]● Not running[/]"
        device_connected = False

    # Check device
    device_did = ""
    if device_connected:
        try:
            resp = requests.get(f"{sdk_url}/device/did", timeout=30)
            device_did = resp.json().get("device_did", "")
        except Exception:
            pass

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="dim", width=20)
    table.add_column("value")

    table.add_row("SDK Daemon", sdk_status)
    table.add_row("Device Connected",
                  "[green]● Yes[/]" if device_connected else "[red]● No[/]")
    if device_did:
        table.add_row("Device DID", Text(device_did[:50], style="cyan"))

    # Check daemon PID
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        table.add_row("Daemon PID", pid)
    else:
        table.add_row("Daemon PID", "[dim]not running[/]")

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# auth test
# ---------------------------------------------------------------------------

def handle_auth(args):
    if args.auth_action == "test":
        auth_test(args)
    else:
        console.print("[yellow]Usage: humanlink auth test[/]")


def auth_test(args):
    """Trigger a test authentication flow via SDK API."""
    import requests
    from bridge.tui import render_auth_request, render_waiting_fingerprint, \
        render_verification_progress, render_result
    from bridge.notifier import notify

    sdk_url = args.sdk_url
    command = args.cmd

    console.print()
    console.print(render_auth_request(command, "high", "test-cli"))

    # 1. Check SDK health
    try:
        resp = requests.get(f"{sdk_url}/health", timeout=20)
        if not resp.ok:
            console.print("[red]SDK daemon not responding.[/]")
            return
    except Exception:
        console.print("[red]SDK daemon not reachable at {sdk_url}[/]")
        console.print("[dim]Start it with: humanlink daemon run --sdk-only[/]")
        return

    # 2. Create challenge
    challenge_data = {
        "action": "exec",
        "action_params": {"command": command},
        "display_title": "命令执行确认",
        "display_summary": command[:256],
        "risk": "high",
        "origin": "local://cli-test",
        "user_id": "local_user",
    }

    try:
        resp = requests.post(f"{sdk_url}/auth/challenge", json=challenge_data, timeout=30)
        if not resp.ok:
            console.print(f"[red]Challenge creation failed: {resp.status_code}[/]")
            return
        result = resp.json()
        session_id = result.get("session_id")
    except Exception as e:
        console.print(f"[red]SDK error: {e}[/]")
        return

    if not session_id:
        console.print("[red]No session_id returned.[/]")
        return

    console.print(f"[dim]Session: {session_id}[/]")

    # 3. Execute authentication
    try:
        resp = requests.post(f"{sdk_url}/auth/execute/{session_id}", timeout=30)
        if not resp.ok:
            console.print(f"[red]Execute failed: {resp.status_code}[/]")
            return
    except Exception as e:
        console.print(f"[red]Execute error: {e}[/]")
        return

    # Notify
    notify("HumanLink", "请触碰 U盾确认操作")

    console.print(render_waiting_fingerprint())

    # 4. Poll for result with live TUI
    deadline = time.time() + 30
    last_step = -1
    step_results: list[bool] = []

    while time.time() < deadline:
        try:
            resp = requests.get(f"{sdk_url}/auth/status/{session_id}", timeout=30)
            if not resp.ok:
                time.sleep(0.5)
                continue
            status_data = resp.json()
            status = status_data.get("status", "")
            device_status = status_data.get("device_status", "")
            user_prompt = status_data.get("user_prompt", "")
            v_step = status_data.get("verification_step")
            v_progress = status_data.get("verification_progress", 0)

            # Show progress
            if user_prompt:
                console.print(f"\r[dim]{user_prompt}[/]", end="")

            # Show verification steps
            if v_step and v_step > last_step:
                for s in range(last_step + 1, v_step):
                    step_results.append(True)
                last_step = v_step

            if status == "completed":
                # Fill remaining steps
                while len(step_results) < 10:
                    step_results.append(True)
                console.print()
                console.print(render_verification_progress(10, step_results))

                assertion = status_data.get("assertion", {})
                console.print(render_result(
                    success=True,
                    assertion_id=assertion.get("id", session_id),
                    device_did=assertion.get("device", {}).get("id", ""),
                    match_score=assertion.get("evidence", {}).get("match_score", 0),
                ))
                return

            elif status == "failed":
                console.print()
                console.print(render_result(
                    success=False,
                    failure_reason=status_data.get("error", "unknown"),
                ))
                return

        except Exception:
            pass

        time.sleep(0.5)

    console.print()
    console.print(render_result(success=False, failure_reason="认证超时"))


if __name__ == "__main__":
    main()
