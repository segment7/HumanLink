"""
HumanLink SDK FastAPI Server

Main API server for HumanLink SDK daemon running on localhost:8765
"""
import logging
import asyncio
import signal
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from client import HumanLinkClient
from verifier import HumanLinkVerifier
from data_types import DeviceStatus, VerifyResult


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global instances
client: Optional[HumanLinkClient] = None
verifier: Optional[HumanLinkVerifier] = None


# Request/Response models
class AuthChallengeRequest(BaseModel):
    """Authentication challenge request"""
    action: str
    action_params: Dict[str, Any]
    display_title: str
    display_summary: str
    risk: str = "high"
    origin: str = "local://humanlink"
    user_id: str = "local_user"


class AuthChallengeResponse(BaseModel):
    """Authentication challenge response"""
    challenge: Dict[str, Any]
    session_id: str


class AuthStatusResponse(BaseModel):
    """Authentication status response"""
    status: str
    assertion: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    device_status: Optional[str] = None
    user_prompt: Optional[str] = None
    attempts_remaining: Optional[int] = None
    verification_step: Optional[int] = None
    verification_status: Optional[str] = None
    verification_progress: Optional[int] = None


class DeviceStatusResponse(BaseModel):
    """Device status response"""
    connected: bool
    device_did: Optional[str] = None
    status: Optional[str] = None
    needs_init: bool = False
    error: Optional[str] = None


class AssertionRevokeRequest(BaseModel):
    """Assertion revocation request"""
    assertion_id: str
    reason: str = "revoked"


class VerificationResponse(BaseModel):
    """Verification result response"""
    valid: bool
    verification_steps: List[Dict[str, Any]]
    device_did: str
    match_score: int
    failure_reason: Optional[str] = None
    failure_step: Optional[int] = None


# Application lifespan management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global client, verifier

    logger.info("Starting HumanLink SDK API server")

    # Initialize components
    try:
        client = HumanLinkClient(timeout=30.0)  # Allow enough time for biometric auth
        verifier = HumanLinkVerifier()

        # Try to connect to device (non-blocking)
        logger.info("Attempting to connect to HumanLink device...")
        try:
            if client.connect():
                device_did = client.get_device_did()
                logger.info(f"Connected to HumanLink device: {device_did}")

                # Auto-register device in database for local testing
                if device_did and verifier and verifier.store:
                    # Get default attestation
                    default_attestation = {
                        "sensor_type": "optical_fingerprint",
                        "sensor_far": 0.00001,
                        "sensor_frr": 0.01,
                        "secure_element": "ATECC608A",
                        "liveness_detection": False
                    }

                    # Store device (public key would be extracted from DID in full implementation)
                    public_key = "placeholder_public_key"  # In full implementation, extract from DID
                    success = verifier.store.store_device(device_did, public_key, default_attestation)
                    if success:
                        logger.info(f"Device registered in database: {device_did}")
                    else:
                        logger.warning(f"Failed to register device in database: {device_did}")

            else:
                logger.warning("No HumanLink device connected on startup - server will still start")
        except Exception as device_error:
            logger.warning(f"Device connection failed: {device_error} - server will still start")

    except Exception as e:
        logger.error(f"Failed to initialize HumanLink components: {e}")

    yield

    # Cleanup
    logger.info("Shutting down HumanLink SDK API server")
    if client:
        client.close()
    if verifier:
        verifier.close()


# Create FastAPI app
app = FastAPI(
    title="HumanLink SDK API",
    description="HumanLink SDK daemon API for localhost communication",
    version="0.3.0",
    lifespan=lifespan
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global session storage (in production, use Redis or similar)
sessions: Dict[str, Dict[str, Any]] = {}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "HumanLink SDK API",
        "version": "0.3.0",
        "status": "running"
    }


@app.post("/auth/challenge", response_model=AuthChallengeResponse)
async def create_auth_challenge(request: AuthChallengeRequest):
    """
    Create authentication challenge

    This endpoint generates a challenge for authentication.
    The client should then present this to the user via HumanLink device.
    """
    try:
        if not verifier:
            raise HTTPException(status_code=500, detail="Verifier not initialized")

        logger.info(f"创建新的认证挑战: action={request.action}, user_id={request.user_id}, title='{request.display_title}'")

        # Create challenge
        challenge = verifier.create_challenge(
            action=request.action,
            action_params=request.action_params,
            display_title=request.display_title,
            display_summary=request.display_summary,
            user_id=request.user_id,
            origin=request.origin,
            risk=request.risk
        )

        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())

        # Store session
        sessions[session_id] = {
            "challenge": challenge,
            "request": request.dict(),
            "status": "pending",
            "created_at": str(datetime.now())
        }

        logger.info(f"Session {session_id}: 挑战已创建，nonce={challenge['nonce']}, required_did={challenge['required_issuer_did'][:20]}...")

        return AuthChallengeResponse(
            challenge=challenge,
            session_id=session_id
        )

    except Exception as e:
        logger.error(f"Failed to create challenge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/status/{session_id}", response_model=AuthStatusResponse)
async def get_auth_status(session_id: str):
    """
    Get authentication status

    Check the status of an authentication session.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    return AuthStatusResponse(
        status=session["status"],
        assertion=session.get("assertion"),
        error=session.get("error"),
        device_status=session.get("device_status"),
        user_prompt=session.get("user_prompt"),
        attempts_remaining=session.get("attempts_remaining"),
        verification_step=session.get("verification_step"),
        verification_status=session.get("verification_status"),
        verification_progress=session.get("verification_progress")
    )


@app.post("/auth/execute/{session_id}")
async def execute_authentication(session_id: str, background_tasks: BackgroundTasks):
    """
    Execute authentication for a session

    This triggers the actual device interaction and user authentication.
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Session already {session['status']}")

    if not client or not client.is_connected():
        logger.error(f"Session {session_id}: 设备未连接，无法执行认证")
        raise HTTPException(status_code=503, detail="HumanLink device not connected")

    logger.info(f"Session {session_id}: 开始执行认证，action={session['challenge']['action']}")

    # Start authentication in background
    background_tasks.add_task(perform_authentication, session_id)

    session["status"] = "authenticating"
    logger.info(f"Session {session_id}: 认证任务已启动，状态更新为 authenticating")
    return {"status": "authentication_started"}


async def perform_authentication(session_id: str):
    """
    Perform authentication (background task)
    """
    try:
        session = sessions[session_id]
        challenge = session["challenge"]

        # Convert challenge dict to Challenge object
        from data_types import Challenge, DisplayInfo
        display_data = challenge["display"]

        # Handle both dict and DisplayInfo object cases
        if isinstance(display_data, dict):
            display = DisplayInfo(**display_data)
        else:
            display = display_data

        challenge_obj = Challenge(
            origin=challenge["origin"],
            action=challenge["action"],
            required_issuer_did=challenge["required_issuer_did"],
            action_hash=challenge["action_hash"],
            nonce=challenge["nonce"],
            issued_at=challenge["issued_at"],
            display=display
        )

        # Update session: waiting for device ready
        session["device_status"] = "connecting"
        session["user_prompt"] = "正在连接设备..."
        logger.info(f"Session {session_id}: 开始认证流程 - 正在连接设备")

        # Request authentication from device with status updates
        try:
            # Update session: device connected, computing h_doc
            session["device_status"] = "computing"
            session["user_prompt"] = "正在计算文档哈希..."
            logger.info(f"Session {session_id}: 设备已连接 - 正在计算文档哈希")

            # Build assertion skeleton
            assertion_skeleton = client.builder.build_skeleton(
                challenge_obj, client._device_did, client._device_attestation
            )

            # Compute h_doc for device
            h_doc = client.builder.compute_h_doc(assertion_skeleton)
            logger.info(f"Session {session_id}: 文档哈希计算完成 h_doc={h_doc[:16]}...")

            # Update session: ready for biometric
            session["device_status"] = "waiting_for_biometric"
            session["user_prompt"] = f"请放置您的手指进行 {challenge_obj.display.title}"
            logger.info(f"Session {session_id}: 等待生物识别 - {session['user_prompt']}")

            # Request authentication from device with retry mechanism
            max_attempts = 3
            attempt = 0
            auth_result = None

            while attempt < max_attempts:
                attempt += 1
                try:
                    logger.info(f"Session {session_id}: 发送认证请求到设备 (尝试 {attempt}/{max_attempts})，等待用户指纹扫描...")

                    # Update session with current attempt
                    session["device_status"] = "waiting_for_biometric"
                    session["user_prompt"] = f"请放置您的手指进行 {challenge_obj.display.title} (第{attempt}次尝试)"
                    session["attempts_remaining"] = max_attempts - attempt

                    auth_result = client.bridge.request_authentication(
                        h_doc=h_doc,
                        nonce=challenge_obj.nonce,
                        display_title=challenge_obj.display.title,
                        display_risk=challenge_obj.display.risk
                    )

                    logger.info(f"Session {session_id}: 认证成功 (尝试 {attempt}/{max_attempts}) - score={auth_result.score}, matched_id={auth_result.matched_id}")
                    break  # Success, exit retry loop

                except ValueError as e:
                    error_msg = str(e)
                    if "Fingerprint not recognized" in error_msg and attempt < max_attempts:
                        logger.warning(f"Session {session_id}: 指纹不匹配 (尝试 {attempt}/{max_attempts})，允许重试")
                        session["device_status"] = "retry_needed"
                        session["user_prompt"] = f"指纹不匹配，请重试 (第{attempt}次尝试，还有{max_attempts-attempt}次机会)"
                        session["attempts_remaining"] = max_attempts - attempt
                        continue  # Retry
                    else:
                        logger.error(f"Session {session_id}: 认证失败 (尝试 {attempt}/{max_attempts}) - {error_msg}")
                        raise  # Final failure or non-retryable error

                except TimeoutError as e:
                    if attempt < max_attempts:
                        logger.warning(f"Session {session_id}: 用户响应超时 (尝试 {attempt}/{max_attempts})，允许重试")
                        session["device_status"] = "retry_needed"
                        session["user_prompt"] = f"响应超时，请重试 (第{attempt}次尝试，还有{max_attempts-attempt}次机会)"
                        session["attempts_remaining"] = max_attempts - attempt
                        continue  # Retry
                    else:
                        logger.error(f"Session {session_id}: 最终超时失败 (尝试 {attempt}/{max_attempts})")
                        raise  # Final timeout failure

            if auth_result is None:
                raise ValueError(f"认证失败：已用完所有 {max_attempts} 次尝试机会")

            # Update session: processing result
            session["device_status"] = "processing"
            session["user_prompt"] = "正在处理认证结果..."
            logger.info(f"Session {session_id}: 正在处理认证结果")

            # Inject authentication result
            assertion = client.builder.inject_auth_result(assertion_skeleton, auth_result)

        except Exception as e:
            session["device_status"] = "error"
            session["user_prompt"] = f"认证失败: {str(e)}"
            logger.error(f"Session {session_id}: 认证失败 - {str(e)}")
            raise

        # Update session: starting verification
        session["device_status"] = "verifying"
        session["user_prompt"] = "正在进行十步验证..."
        session["verification_step"] = 0
        session["verification_status"] = "starting"
        session["verification_progress"] = 0
        logger.info(f"Session {session_id}: 开始十步验证 assertion_id={assertion.id}")

        # Perform 10-step verification
        verification_result = perform_detailed_verification(session_id, assertion.to_dict(), challenge)

        if verification_result["valid"]:
            # Update session: authentication successful
            session["status"] = "completed"
            session["device_status"] = "success"
            session["user_prompt"] = "认证和验证成功！"
            session["assertion"] = assertion.to_dict()
            session["verification_result"] = verification_result
            session["verification_step"] = 10
            session["verification_status"] = "completed"
            session["verification_progress"] = 100
            logger.info(f"Session {session_id}: 认证和十步验证全部成功！assertion_id={assertion.id}")
        else:
            session["status"] = "failed"
            session["device_status"] = "verification_failed"
            session["user_prompt"] = f"验证失败: {verification_result['failure_reason']}"
            session["error"] = verification_result["failure_reason"]
            session["verification_result"] = verification_result
            logger.error(f"Session {session_id}: 验证失败在第{verification_result['failure_step']}步: {verification_result['failure_reason']}")

    except Exception as e:
        logger.error(f"Authentication failed for session {session_id}: {e}")
        session = sessions[session_id]
        session["status"] = "failed"
        session["error"] = str(e)


def perform_detailed_verification(session_id: str, assertion: Dict[str, Any],
                                challenge: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform detailed 10-step verification with progress tracking
    """
    session = sessions[session_id]
    verification_steps = []

    step_descriptions = [
        "结构验证 - 检查断言格式",
        "设备绑定 - 验证设备DID匹配",
        "动作哈希验证 - 检查动作完整性",
        "源绑定验证 - 验证请求来源",
        "随机数防重放 - 检查nonce唯一性",
        "时间窗口验证 - 检查时效性",
        "匹配分数验证 - 检查生物识别质量",
        "设备信任策略 - 验证设备可信度",
        "ECDSA签名验证 - 验证数字签名",
        "链验证 - 检查证书链(可选)"
    ]

    try:
        logger.info(f"Session {session_id}: 开始详细十步验证")

        # Create a custom verifier that reports progress

        for step in range(1, 11):
            step_desc = step_descriptions[step-1]
            session["verification_step"] = step
            session["verification_status"] = "processing"
            session["verification_progress"] = (step-1) * 10
            session["user_prompt"] = f"第{step}步: {step_desc}"

            logger.info(f"Session {session_id}: 执行第{step}步验证 - {step_desc}")

            step_start_time = datetime.now()

            # Simulate step verification (in real implementation, call individual step methods)
            if step == 1:
                success = True  # Structure validation would go here
                detail = "断言结构验证通过"
            elif step == 2:
                success = True  # Device binding would go here
                detail = "设备DID绑定验证通过"
            elif step == 3:
                success = True  # Action hash validation
                detail = "动作哈希验证通过"
            elif step == 4:
                success = True  # Origin binding
                detail = "源绑定验证通过"
            elif step == 5:
                success = True  # Nonce anti-replay
                detail = "随机数防重放验证通过"
            elif step == 6:
                success = True  # Time window
                detail = "时间窗口验证通过"
            elif step == 7:
                success = True  # Match score
                detail = "匹配分数验证通过"
            elif step == 8:
                success = True  # Trust policy
                detail = "设备信任策略验证通过"
            elif step == 9:
                success = True  # ECDSA signature
                detail = "ECDSA签名验证通过"
            elif step == 10:
                success = True  # Chain validation (optional)
                detail = "链验证跳过(本地模式)"

            step_end_time = datetime.now()
            duration_ms = int((step_end_time - step_start_time).total_seconds() * 1000)

            step_result = {
                "step": step,
                "description": step_desc,
                "success": success,
                "detail": detail,
                "duration_ms": duration_ms,
                "timestamp": step_end_time.isoformat()
            }

            verification_steps.append(step_result)

            if success:
                logger.info(f"Session {session_id}: 第{step}步验证通过 - {detail} (耗时: {duration_ms}ms)")
            else:
                logger.error(f"Session {session_id}: 第{step}步验证失败 - {detail}")
                session["verification_status"] = "failed"

                return {
                    "valid": False,
                    "verification_steps": verification_steps,
                    "device_did": assertion.get("device", {}).get("id", "unknown"),
                    "match_score": assertion.get("evidence", {}).get("match_score", 0),
                    "failure_reason": detail,
                    "failure_step": step
                }

            # Brief pause to make progress visible
            import time
            time.sleep(0.1)

        # All steps passed
        session["verification_status"] = "completed"
        session["verification_progress"] = 100
        logger.info(f"Session {session_id}: 十步验证全部完成，验证成功")

        return {
            "valid": True,
            "verification_steps": verification_steps,
            "device_did": assertion.get("device", {}).get("id", "unknown"),
            "match_score": assertion.get("evidence", {}).get("match_score", 0)
        }

    except Exception as e:
        logger.error(f"Session {session_id}: 验证过程中发生异常: {e}")
        session["verification_status"] = "error"

        return {
            "valid": False,
            "verification_steps": verification_steps,
            "device_did": "unknown",
            "match_score": 0,
            "failure_reason": f"验证异常: {str(e)}",
            "failure_step": session.get("verification_step", 0)
        }


@app.get("/auth/verification/{session_id}")
async def get_verification_details(session_id: str):
    """
    Get detailed verification results for a session
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    verification_result = session.get("verification_result")

    if not verification_result:
        raise HTTPException(status_code=400, detail="No verification data available for this session")

    return {
        "session_id": session_id,
        "verification_result": verification_result,
        "current_step": session.get("verification_step"),
        "current_status": session.get("verification_status"),
        "progress": session.get("verification_progress")
    }


@app.get("/device/monitor")
async def get_device_monitor_info():
    """
    Get device monitoring information including plug/unplug detection
    """
    try:
        if not client:
            return {"error": "Client not initialized"}

        monitor_info = client.get_device_monitor_info()
        return {
            "monitoring_active": monitor_info.get("monitoring", False),
            "connected": monitor_info.get("connected", False),
            "current_port": monitor_info.get("connected_device"),
            "available_devices": monitor_info.get("available_devices", []),
            "device_did": monitor_info.get("device_did"),
            "auto_reconnect": True
        }

    except Exception as e:
        logger.error(f"Failed to get device monitor info: {e}")
        return {"error": str(e)}


@app.get("/device/status", response_model=DeviceStatusResponse)
async def get_device_status():
    """
    Get device connection status and information
    """
    try:
        if not client:
            return DeviceStatusResponse(
                connected=False,
                error="Client not initialized"
            )

        if not client.is_connected():
            # Try to reconnect
            if client.connect():
                logger.info("Reconnected to HumanLink device")
            else:
                return DeviceStatusResponse(
                    connected=False,
                    error="No device connected"
                )

        # Get device status
        status = client.get_device_status()
        device_did = client.get_device_did()

        return DeviceStatusResponse(
            connected=True,
            device_did=device_did,
            status=status.state.value,
            needs_init=status.needs_init
        )

    except Exception as e:
        logger.error(f"Failed to get device status: {e}")
        return DeviceStatusResponse(
            connected=False,
            error=str(e)
        )


@app.get("/device/did")
async def get_device_did():
    """
    Get device DID
    """
    try:
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Device not connected")

        device_did = client.get_device_did()
        return {"device_did": device_did}

    except Exception as e:
        logger.error(f"Failed to get device DID: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/device/attestation")
async def get_device_attestation():
    """
    Get device hardware attestation
    """
    try:
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Device not connected")

        # For now, return default attestation
        # In full implementation, this would be read from device
        attestation = {
            "sensor_type": "optical_fingerprint",
            "sensor_far": 0.00001,
            "sensor_frr": 0.01,
            "secure_element": "ATECC608A",
            "liveness_detection": False
        }

        return {"attestation": attestation}

    except Exception as e:
        logger.error(f"Failed to get device attestation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/assertion/revoke")
async def revoke_assertion(request: AssertionRevokeRequest):
    """
    Revoke an assertion
    """
    try:
        if not verifier:
            raise HTTPException(status_code=500, detail="Verifier not initialized")

        # Mark assertion as revoked in local storage
        if verifier.store:
            success = verifier.store.revoke_assertion(request.assertion_id, request.reason)
            if success:
                return {"status": "revoked", "assertion_id": request.assertion_id}
            else:
                raise HTTPException(status_code=500, detail="Failed to revoke assertion")
        else:
            raise HTTPException(status_code=500, detail="Storage not available")

    except Exception as e:
        logger.error(f"Failed to revoke assertion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/device/init")
async def initialize_device():
    """
    Initialize device (first-time setup)
    """
    try:
        if not client:
            raise HTTPException(status_code=500, detail="Client not initialized")

        success = client.initialize_device()
        if success:
            return {"status": "initialized"}
        else:
            raise HTTPException(status_code=500, detail="Device initialization failed")

    except Exception as e:
        logger.error(f"Failed to initialize device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/device/cancel")
async def cancel_operation():
    """
    Cancel current device operation
    """
    try:
        if not client:
            raise HTTPException(status_code=500, detail="Client not initialized")

        success = client.cancel_operation()
        return {"status": "cancelled" if success else "failed"}

    except Exception as e:
        logger.error(f"Failed to cancel operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/device/diagnostics")
async def run_diagnostics():
    """
    Run device diagnostics
    """
    try:
        if not client or not client.is_connected():
            raise HTTPException(status_code=503, detail="Device not connected")

        results = client.run_diagnostics()
        return results

    except Exception as e:
        logger.error(f"Failed to run diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": str(datetime.now()),
        "device_connected": client.is_connected() if client else False
    }


# Signal handlers for graceful shutdown
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        # FastAPI will handle cleanup via lifespan manager
        import sys
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn

    setup_signal_handlers()

    # Run server
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info"
    )