from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, List, Union
from pydantic import BaseModel
from .auth import DiscordAuthService
from auth import decode_jwt
import json
import hmac
import hashlib
import os

router = APIRouter(prefix="/api/discord", tags=["discord"])


# Discord Interaction Handler (버튼 클릭 처리 - URL 없이 바로 실행)
@router.post("/interactions")
async def handle_interactions(request: Request):
    """
    Discord에서 버튼 클릭 시 호출되는 Interaction 엔드포인트.
    Discord Developer Portal > Bot > Interactions Endpoint URL 에 이 URL을 등록해야 함.
    
    예: https://your-backend.com/api/discord/interactions
    """
    body = await request.body()
    body_text = body.decode("utf-8")
    
    # 1) Discord 서명 검증 (보안 필수)
    public_key = os.getenv("DISCORD_PUBLIC_KEY", "")
    if public_key:
        signature = request.headers.get("X-Signature-Ed25519", "")
        timestamp   = request.headers.get("X-Signature-Timestamp", "")
        try:
            from nacl.signing import VerifyKey
            from nacl.exceptions import BadSignatureError
            verify_key = VerifyKey(bytes.fromhex(public_key))
            verify_key.verify(f"{timestamp}{body_text}".encode(), bytes.fromhex(signature))
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid request signature")
    
    data = json.loads(body_text)
    interaction_type = data.get("type")
    
    # 2) Ping (Discord 등록 확인용)
    if interaction_type == 1:
        return JSONResponse({"type": 1})
    
    # 3) 버튼 클릭 (Component Interaction)
    if interaction_type == 3:
        custom_id = data.get("data", {}).get("custom_id", "")
        
        # custom_id 형식: "save:<index>:<user_email>" 또는 구형 "save:<paper_id>"
        if custom_id.startswith("save:"):
            try:
                parts = custom_id.split(":", 2)
                
                paper_id = ""
                user_email = ""
                title = ""
                summary = ""
                link = ""
                
                if len(parts) == 3:
                    _, str_index_or_http, user_email_or_url = parts
                    
                    try:
                        # 1. 신형 버튼 로직 (str_index가 숫자일 경우)
                        embed_index = int(str_index_or_http)
                        user_email = user_email_or_url
                        
                        message_data = data.get("message", {})
                        embeds = message_data.get("embeds", [])
                        # 0번은 Summary, 1번부터 실제 논문 Embed (notifications.py 로직)
                        target_embed = embeds[embed_index + 1] if len(embeds) > embed_index + 1 else {}
                        
                        raw_title = target_embed.get("title", "")
                        import re
                        title = re.sub(r'^\d+\.\s*', '', raw_title)
                        link = target_embed.get("url", "")
                        summary = target_embed.get("description", "")
                        paper_id = link.split("/")[-1] if link else title
                        
                    except ValueError:
                        # 2. 구형 버튼 로직 (str_index가 'http'일 경우)
                        paper_id_raw = f"{str_index_or_http}:{user_email_or_url}"
                        paper_id = paper_id_raw.split("/")[-1]
                        link = paper_id_raw
                        # 이메일 정보 추출 시도
                        if "@" in user_email_or_url:
                            user_email = user_email_or_url
                
                # 제목이나 요약이 비어있다면 DB에서 강제 복원
                if not title or not summary or title.strip() == "":
                    try:
                        from database import get_connection
                        conn = get_connection()
                        cursor = conn.cursor()
                        clean_id = paper_id.split("/")[-1] if "/" in paper_id else paper_id
                        cursor.execute("""
                            SELECT title, summary, abstract FROM papers 
                            WHERE arxiv_id LIKE %s OR id = %s
                            LIMIT 1
                        """, (f"%{clean_id}%", clean_id))
                        row = cursor.fetchone()
                        if row:
                            title = row[0] if row[0] else title
                            summary = row[1] or row[2] or summary
                        conn.close()
                    except Exception as db_err:
                        print(f"[DEBUG] DB Fallback error: {db_err}")
                
                # 그래도 이메일이 없다면 실패 응답
                if not user_email or "@" not in user_email:
                    return JSONResponse({
                        "type": 4,
                        "data": {
                            "content": "❌ 이메일 정보를 찾을 수 없습니다. 새로운 알림에서 버튼을 눌러주세요.",
                            "flags": 64
                        }
                    })

                # 보관함에 최종 저장
                from storage_box.service import StorageBoxService
                result = StorageBoxService.save_bookmark(user_email, {
                    "id": paper_id,
                    "title": title if title and title.strip() else "제목 없음",
                    "summary": summary if summary else "",
                    "link": link if link else "",
                    "source": "discord_bot"
                })
                
                if result.get("ok"):
                    return JSONResponse({
                        "type": 4,
                        "data": {
                            "content": "✅ 논문이 보관함에 저장되었습니다!",
                            "flags": 64
                        }
                    })
                else:
                    return JSONResponse({
                        "type": 4,
                        "data": {
                            "content": f"❌ 저장 실패: {result.get('error')}",
                            "flags": 64
                        }
                    })
            except Exception as e:
                return JSONResponse({
                    "type": 4,
                    "data": {
                        "content": f"❌ 오류 발생: {str(e)}",
                        "flags": 64
                    }
                })
    
    return JSONResponse({"type": 1})


class ChannelSelectRequest(BaseModel):
    guild_id: str
    channel_id: Union[str, List[str]]

def get_email_from_token(authorization: Optional[str] = Header(None)) -> str:
    """Authorization 헤더에서 email 추출"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    token = authorization.split(" ", 1)[1]
    payload = decode_jwt(token)
    return payload["email"]

# Phase 2: Discord OAuth
@router.get("/oauth-url")
def get_oauth_url(authorization: Optional[str] = Header(None)):
    """
    Discord OAuth URL 반환
    프론트에서 이 URL로 팝업을 띄우고 리다이렉트 처리
    """
    try:
        user_email = get_email_from_token(authorization)
        oauth_url = DiscordAuthService.get_oauth_url(state=user_email)
        return {
            "ok": True,
            "oauth_url": oauth_url,
            "message": "Discord OAuth URL 생성 완료"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "OAuth URL 생성 실패"
        }

@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """
    Discord OAuth callback 처리
    프론트에서 OAuth 완료 후 리다이렉트되는 엔드포인트
    """
    try:
        user_email = state  # state에 user_email을 담음
        result = await DiscordAuthService.handle_oauth_callback(code, user_email)
        
        if result.get("ok"):
                        # # 연결 완료 후 팝업을 닫고 부모 창에 완료 신호를 보냄
                        return HTMLResponse(
                                content=f"""
                                <!doctype html>
                                <html lang="ko">
                                    <head>
                                        <meta charset="utf-8" />
                                        <title>Discord 연결 완료</title>
                                    </head>
                                    <body>
                                        <p>Discord 연결이 완료되었습니다. 창을 닫아도 됩니다.</p>
                                        <script>
                                            try {{
                                                if (window.opener) {{
                                                    window.opener.postMessage({{
                                                        type: 'discord-oauth-complete',
                                                        ok: true,
                                                        discord_username: {result.get('discord_username')!r},
                                                        discord_user_id: {result.get('discord_user_id')!r}
                                                    }}, '*');
                                                }}
                                            }} catch (e) {{}}
                                            setTimeout(() => window.close(), 300);
                                        </script>
                                    </body>
                                </html>
                                """,
                                status_code=200,
                        )
        else:
                        return HTMLResponse(
                                content=f"""
                                <!doctype html>
                                <html lang="ko">
                                    <head><meta charset="utf-8" /><title>Discord 연결 실패</title></head>
                                    <body>
                                        <p>Discord 연결에 실패했습니다. 다시 시도해주세요.</p>
                                        <script>
                                            try {{
                                                if (window.opener) {{
                                                    window.opener.postMessage({{
                                                        type: 'discord-oauth-complete',
                                                        ok: false,
                                                        message: {result.get('message', 'Discord 연결 실패')!r}
                                                    }}, '*');
                                                }}
                                            }} catch (e) {{}}
                                        </script>
                                    </body>
                                </html>
                                """,
                                status_code=400,
                        )
    except Exception as e:
                return HTMLResponse(
                        content=f"""
                        <!doctype html>
                        <html lang="ko">
                            <head><meta charset="utf-8" /><title>Discord 연결 실패</title></head>
                            <body>
                                <p>Discord 연결 처리 중 오류가 발생했습니다.</p>
                                <script>
                                    try {{
                                        if (window.opener) {{
                                            window.opener.postMessage({{
                                                type: 'discord-oauth-complete',
                                                ok: false,
                                                message: {str(e)!r}
                                            }}, '*');
                                        }}
                                    }} catch (err) {{}}
                                </script>
                            </body>
                        </html>
                        """,
                        status_code=400,
                )


# env(.env)와 호환되는 이전/대체 callback 경로
@router.get("/callback")
async def oauth_callback_compat(
    code: str = Query(...),
    state: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    return await oauth_callback(code=code, state=state, authorization=authorization)

@router.get("/status")
def get_connection_status(authorization: Optional[str] = Header(None)):
    """
    사용자의 Discord 연결 상태 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        result = DiscordAuthService.get_connection_status(user_email)
        return result
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "상태 조회 실패"
        }


@router.get("/channels")
async def get_available_channels(authorization: Optional[str] = Header(None)):
    """
    Discord 연결 사용자가 선택 가능한 채널 목록 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        return await DiscordAuthService.list_available_channels(user_email)
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "채널 목록 조회 실패"
        }


@router.patch("/channel")
def set_selected_channel(
    request: ChannelSelectRequest,
    authorization: Optional[str] = Header(None)
):
    """
    테스트/알림 전송 대상 채널 선택 저장
    """
    try:
        user_email = get_email_from_token(authorization)
        return DiscordAuthService.set_selected_channel(
            user_email=user_email,
            guild_id=request.guild_id,
            channel_id=request.channel_id,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "채널 선택 저장 실패"
        }
