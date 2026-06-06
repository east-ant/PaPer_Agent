# email_module/router.py — 이메일 인증 API
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import decode_jwt, create_jwt
from database import get_connection
from .service import send_auth_code, verify_auth_code, send_test_notification
import pymysql

router = APIRouter(prefix="/api/auth/email", tags=["email_auth"])


def _get_email_from_token(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    token = authorization.split(" ", 1)[1]
    payload = decode_jwt(token)
    return payload["email"]


class SendCodeRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


# ─── 인증 코드 발송 ───────────────────────────────────────────────────────────

@router.post("/send-code")
def send_code(request: SendCodeRequest):
    """이메일로 OTP 인증 코드 발송"""
    email = request.email.strip().lower()
    if not email or "@" not in email:
        return {"ok": False, "message": "이메일 형식이 올바르지 않습니다."}

    result = send_auth_code(email)
    return result


# ─── 인증 코드 검증 ───────────────────────────────────────────────────────────

@router.post("/verify-code")
def verify_code(request: VerifyCodeRequest):
    """OTP 검증 — 성공 시 JWT 발급"""
    email = request.email.strip().lower()
    code = request.code.strip()

    result = verify_auth_code(email, code)
    if not result.get("ok"):
        return result

    # JWT 발급
    token = create_jwt({"email": email, "name": email.split("@")[0], "picture": ""})
    return {
        "ok": True,
        "message": "인증 성공",
        "token": token,
        "user": {"email": email, "name": email.split("@")[0]},
    }


# ─── 테스트 알림 발송 ─────────────────────────────────────────────────────────

@router.post("/test")
def test_email(authorization: Optional[str] = Header(None)):
    """현재 로그인 이메일로 테스트 알림 발송"""
    user_email = _get_email_from_token(authorization)
    result = send_test_notification(user_email)
    return result


# ─── 이메일 연결 상태 조회 ────────────────────────────────────────────────────

@router.get("/status")
def email_status(authorization: Optional[str] = Header(None)):
    """이메일 알림 채널 연결 상태 조회"""
    user_email = _get_email_from_token(authorization)
    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            "SELECT email_connected, email_address FROM notification_settings WHERE user_email = %s LIMIT 1",
            (user_email,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"ok": True, "connected": bool(row.get("email_connected")), "email": row.get("email_address")}
        return {"ok": True, "connected": False, "email": None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
