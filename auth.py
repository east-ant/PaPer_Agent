# auth.py
import urllib.parse
import requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from config import settings
from database import save_user

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
REDIRECT_URI = "http://localhost:8000/auth/google/callback"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def create_jwt(user: dict) -> str:
    payload = {
        "sub": user["email"],
        "name": user["name"],
        "email": user["email"],
        "picture": user.get("picture", ""),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")


@router.get("/google")
def google_login():
    """구글 로그인 페이지로 리다이렉트"""
    params = urllib.parse.urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback")
def google_callback(code: str):
    """구글이 code를 전달하면 토큰 교환 후 JWT 발급"""
    # 1. code → access_token 교환
    token_res = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    if not token_res.ok:
        raise HTTPException(status_code=400, detail="구글 토큰 교환 실패")

    access_token = token_res.json().get("access_token")

    # 2. access_token → 유저 정보
    user_res = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not user_res.ok:
        raise HTTPException(status_code=400, detail="유저 정보 조회 실패")

    user = user_res.json()  # email, name, picture, sub

    save_user(                 
        email=user["email"],
        name=user.get("name", ""),
        picture=user.get("picture", ""),
    )

    token = create_jwt(user)
    frontend_redirect = f"{settings.frontend_url}/auth/callback?token={token}"
    return RedirectResponse(frontend_redirect)


@router.get("/me")
def get_me(token: str):
    """JWT 검증 후 유저 정보 반환 — 프론트가 Authorization 헤더 대신 쿼리로 써도 됨"""
    return decode_jwt(token)