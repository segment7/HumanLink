"""
HumanLink Rich TUI

Terminal-based real-time display for biometric authorization flow.
"""
import time
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.layout import Layout
from rich.align import Align

console = Console()

# Verification step descriptions
VERIFY_STEPS = [
    "结构验证 — 检查断言格式",
    "设备绑定 — 验证设备 DID",
    "动作哈希 — 校验操作完整性",
    "源绑定 — 验证请求来源",
    "防重放 — 检查 nonce 唯一性",
    "时间窗口 — 校验时效性",
    "匹配分数 — 生物识别质量",
    "设备信任 — 验证设备可信度",
    "ECDSA 签名 — 数字签名验证",
    "链上校验 — 证书链验证",
]


def render_auth_request(command: str, risk: str = "high", agent_id: str = "",
                        session_key: str = "") -> Panel:
    """Render the initial authorization request panel."""
    risk_color = {"high": "red", "medium": "yellow", "low": "green"}.get(risk, "red")
    risk_bar = "█" * 10 if risk == "high" else "█" * 6 + "░" * 4

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("label", style="dim", width=12)
    table.add_column("value")

    table.add_row("Action", Text(command[:120], style="bold white"))
    table.add_row("Risk", Text(f"{risk_bar} {risk.upper()}", style=f"bold {risk_color}"))
    if agent_id:
        table.add_row("Agent", Text(agent_id, style="cyan"))
    if session_key:
        table.add_row("Session", Text(session_key[:32], style="dim"))

    return Panel(
        table,
        title="[bold yellow]HumanLink Authorization[/]",
        border_style="yellow",
        padding=(1, 2),
    )


def render_waiting_fingerprint() -> Panel:
    """Render the 'waiting for fingerprint' panel."""
    content = Align.center(
        Text("▶ 请触碰 U盾确认...", style="bold cyan blink"),
    )
    return Panel(content, border_style="cyan", padding=(1, 2))


def render_verification_progress(current_step: int, step_results: list[bool]) -> Table:
    """Render the 10-step verification progress."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("step", width=8)
    table.add_column("desc")
    table.add_column("status", width=4, justify="right")

    for i, desc in enumerate(VERIFY_STEPS):
        step_num = f"[{i + 1}/10]"
        if i < len(step_results):
            if step_results[i]:
                status = "[green]✓[/]"
                style = "green"
            else:
                status = "[red]✗[/]"
                style = "red"
        elif i == current_step:
            status = "[yellow]⟳[/]"
            style = "yellow"
        else:
            status = "[dim]·[/]"
            style = "dim"

        table.add_row(
            Text(step_num, style=style),
            Text(desc, style=style),
            status,
        )

    return table


def render_result(success: bool, assertion_id: str = "", device_did: str = "",
                  match_score: int = 0, failure_reason: str = "") -> Panel:
    """Render the final result panel."""
    if success:
        lines = [
            Text("授权成功", style="bold green"),
            Text(""),
        ]
        if assertion_id:
            lines.append(Text(f"Assertion: {assertion_id[:36]}", style="dim"))
        if device_did:
            lines.append(Text(f"Device:    {device_did[:40]}", style="dim"))
        if match_score:
            lines.append(Text(f"Score:     {match_score}", style="dim"))

        content = Text("\n").join(lines)
        return Panel(content, border_style="green", padding=(1, 2))
    else:
        content = Text(f"授权失败: {failure_reason}", style="bold red")
        return Panel(content, border_style="red", padding=(1, 2))


class AuthTUI:
    """Interactive TUI for a single authorization flow."""

    def __init__(self):
        self.console = Console()

    def show_full_flow(self, command: str, risk: str = "high",
                       agent_id: str = "", session_key: str = "",
                       auth_callback=None):
        """
        Display the full authorization flow in terminal.

        auth_callback: async callable that performs the actual auth.
          Returns dict with keys: success, assertion_id, device_did,
          match_score, failure_reason, step_updates (generator/list).
        """
        # 1. Show request
        self.console.print()
        self.console.print(render_auth_request(command, risk, agent_id, session_key))

        # 2. Waiting for fingerprint
        self.console.print(render_waiting_fingerprint())

        return self  # caller drives the steps

    def show_verification(self, step: int, results: list[bool]):
        """Update verification display."""
        self.console.print(render_verification_progress(step, results))

    def show_result(self, success: bool, **kwargs):
        """Show final result."""
        self.console.print(render_result(success, **kwargs))
        self.console.print()


def demo_flow():
    """Demo the TUI flow with simulated data."""
    tui = AuthTUI()
    console.print()

    # Request
    console.print(render_auth_request(
        command="rm -rf /home/user/important",
        risk="high",
        agent_id="claude-code",
        session_key="sess-abc123",
    ))

    # Waiting
    console.print(render_waiting_fingerprint())
    time.sleep(1.5)

    # Verification progress
    results: list[bool] = []
    for i in range(10):
        console.clear()
        console.print(render_auth_request(
            command="rm -rf /home/user/important",
            risk="high",
            agent_id="claude-code",
        ))
        results.append(True)
        console.print(render_verification_progress(i + 1, results))
        time.sleep(0.3)

    # Result
    console.print()
    console.print(render_result(
        success=True,
        assertion_id="urn:uuid:550e8400-e29b-41d4-a716-446655440000",
        device_did="did:key:z6MkBob...",
        match_score=188,
    ))


if __name__ == "__main__":
    demo_flow()
