"""
HumanLink Gateway Bridge

Connects to any OpenClaw-compatible Gateway via WebSocket,
listens for exec.approval.requested events, triggers HumanLink
biometric auth, and resolves the approval.

Gateway code: ZERO changes required.
SDK code: ZERO changes required.
"""
import asyncio
import json
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass

import websockets

from .notifier import notify
from .tui import AuthTUI, render_auth_request, render_waiting_fingerprint, \
    render_verification_progress, render_result

logger = logging.getLogger(__name__)


@dataclass
class GatewayConfig:
    """Gateway connection configuration."""
    url: str = "ws://127.0.0.1:18789"
    token: str = ""
    scopes: list[str] = None

    def __post_init__(self):
        if self.scopes is None:
            self.scopes = ["operator.admin"]


@dataclass
class SdkConfig:
    """HumanLink SDK daemon configuration."""
    url: str = "http://127.0.0.1:8765"
    timeout_seconds: int = 30
    poll_interval: float = 0.5


class HumanLinkBridge:
    """
    Bridge between Gateway exec approvals and HumanLink SDK.

    Listens for exec.approval.requested → triggers biometric auth →
    resolves with allow-once or deny.
    """

    def __init__(self, gateway: GatewayConfig, sdk: SdkConfig,
                 on_auth_request: Optional[Callable] = None,
                 on_auth_result: Optional[Callable] = None):
        self.gateway = gateway
        self.sdk = sdk
        self.on_auth_request = on_auth_request
        self.on_auth_result = on_auth_result
        self._ws = None
        self._running = False
        self._msg_id = 0

    async def start(self):
        """Connect to Gateway and start listening."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_listen()
            except (websockets.exceptions.ConnectionClosed, ConnectionRefusedError) as e:
                logger.warning(f"Gateway connection lost: {e}, reconnecting in 3s...")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Bridge error: {e}, reconnecting in 5s...")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the bridge."""
        self._running = False
        if self._ws:
            await self._ws.close()

    async def _connect_and_listen(self):
        """Connect to Gateway WebSocket and process messages."""
        logger.info(f"Connecting to Gateway: {self.gateway.url}")

        async with websockets.connect(self.gateway.url) as ws:
            self._ws = ws

            # Send connect handshake
            await self._send_connect(ws)

            # Wait for hello response
            hello = await ws.recv()
            hello_data = json.loads(hello)
            logger.info(f"Gateway connected: {hello_data.get('method', 'unknown')}")

            # Listen for events
            async for message in ws:
                try:
                    frame = json.loads(message)
                    await self._handle_frame(frame, ws)
                except json.JSONDecodeError:
                    logger.debug(f"Non-JSON message: {message[:100]}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

    async def _send_connect(self, ws):
        """Send the connect handshake to Gateway."""
        connect_msg = {
            "method": "connect",
            "params": {
                "token": self.gateway.token,
                "client": {
                    "id": "humanlink-bridge",
                    "displayName": "HumanLink Bridge",
                    "version": "0.3.0",
                },
                "scopes": self.gateway.scopes,
            },
        }
        await ws.send(json.dumps(connect_msg))

    async def _handle_frame(self, frame: dict, ws):
        """Handle incoming WebSocket frame."""
        # Event frames have "event" field
        event = frame.get("event")
        if not event:
            return

        if event == "exec.approval.requested":
            payload = frame.get("payload", {})
            await self._handle_approval_request(payload, ws)

        elif event == "plugin.approval.requested":
            payload = frame.get("payload", {})
            await self._handle_approval_request(payload, ws)

    async def _handle_approval_request(self, payload: dict, ws):
        """Handle an exec approval request by triggering HumanLink auth."""
        approval_id = payload.get("id", "")
        request = payload.get("request", {})
        command = request.get("command", "unknown")
        agent_id = request.get("agentId", "")
        expires_at = payload.get("expiresAtMs", 0)

        logger.info(f"Approval request: {approval_id} — {command}")

        # Notify via OS notification
        notify(
            "HumanLink 授权请求",
            f"Agent 请求执行: {command[:80]}\n请触碰 U盾确认",
        )

        # Callback for TUI display
        if self.on_auth_request:
            self.on_auth_request(command=command, agent_id=agent_id, approval_id=approval_id)

        # Call HumanLink SDK
        success = await self._authenticate_via_sdk(command, agent_id)

        # Resolve the approval
        decision = "allow-once" if success else "deny"
        await self._resolve_approval(ws, approval_id, decision)

        # Callback for result
        if self.on_auth_result:
            self.on_auth_result(approval_id=approval_id, decision=decision)

    async def _authenticate_via_sdk(self, command: str, agent_id: str) -> bool:
        """Call HumanLink SDK to perform biometric authentication."""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                # 1. Create challenge
                challenge_data = {
                    "action": "exec",
                    "action_params": {"command": command},
                    "display_title": "命令执行确认",
                    "display_summary": command[:256],
                    "risk": "high",
                    "origin": "local://gateway",
                    "user_id": agent_id or "local_user",
                }

                async with session.post(
                    f"{self.sdk.url}/auth/challenge",
                    json=challenge_data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"SDK challenge failed: {resp.status}")
                        return False
                    result = await resp.json()
                    session_id = result.get("session_id")

                if not session_id:
                    logger.error("No session_id from SDK")
                    return False

                # 2. Execute authentication
                async with session.post(
                    f"{self.sdk.url}/auth/execute/{session_id}",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"SDK execute failed: {resp.status}")
                        return False

                # 3. Poll for result
                deadline = time.time() + self.sdk.timeout_seconds
                while time.time() < deadline:
                    try:
                        async with session.get(
                            f"{self.sdk.url}/auth/status/{session_id}",
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            if resp.status != 200:
                                await asyncio.sleep(self.sdk.poll_interval)
                                continue
                            status_data = await resp.json()
                            status = status_data.get("status", "")

                            if status == "completed":
                                logger.info("HumanLink auth: approved")
                                return True
                            elif status == "failed":
                                logger.info(f"HumanLink auth: denied — {status_data.get('error', '')}")
                                return False
                    except Exception as poll_err:
                        logger.debug(f"Poll retry: {type(poll_err).__name__}: {poll_err}")

                    await asyncio.sleep(self.sdk.poll_interval)

                logger.warning("HumanLink auth: timeout")
                return False

        except Exception as e:
            logger.error(f"SDK communication error: {e}")
            return False

    async def _resolve_approval(self, ws, approval_id: str, decision: str):
        """Send exec.approval.resolve to Gateway."""
        self._msg_id += 1
        resolve_msg = {
            "id": self._msg_id,
            "method": "exec.approval.resolve",
            "params": {
                "id": approval_id,
                "decision": decision,
            },
        }
        await ws.send(json.dumps(resolve_msg))
        logger.info(f"Approval {approval_id}: resolved → {decision}")
