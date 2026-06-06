"""
Discord OAuth 인증 및 토큰 관리
"""
import httpx
import pymysql
import json
from typing import Union, List, Optional
from datetime import datetime, timedelta
from config import settings
from database import get_connection

class DiscordAuthService:
    DISCORD_OAUTH_URL = "https://discord.com/api/v10/oauth2/authorize"
    DISCORD_TOKEN_URL = "https://discord.com/api/v10/oauth2/token"
    DISCORD_API_URL = "https://discord.com/api/v10"

    @staticmethod
    def _get_table_columns(table_name: str) -> set[str]:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SHOW COLUMNS FROM {table_name}")
            return {row[0] for row in cursor.fetchall()}
        finally:
            conn.close()

    @staticmethod
    def _get_oauth_tokens(user_email: str) -> tuple[str | None, str | None]:
        columns = DiscordAuthService._get_table_columns("notification_settings")
        where_clause = "user_email=%s" if "user_email" in columns else "user_id=%s"
        access_col = "discord_access_token" if "discord_access_token" in columns else None
        refresh_col = "discord_refresh_token" if "discord_refresh_token" in columns else None
        if not access_col:
            return None, None

        conn = get_connection()
        try:
            cursor = conn.cursor()
            fields = [access_col]
            if refresh_col:
                fields.append(refresh_col)
            cursor.execute(
                f"SELECT {', '.join(fields)} FROM notification_settings WHERE {where_clause} ORDER BY id DESC LIMIT 1",
                (user_email,),
            )
            row = cursor.fetchone()
            if not row:
                return None, None
            access_token = row[0]
            refresh_token = row[1] if len(row) > 1 else None
            return access_token, refresh_token
        finally:
            conn.close()

    @staticmethod
    async def list_available_channels(user_email: str) -> dict:
        access_token, _ = DiscordAuthService._get_oauth_tokens(user_email)
        if not settings.discord_bot_token:
            return {"ok": False, "message": "DISCORD_BOT_TOKEN 설정이 필요합니다"}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                user_guild_ids = None
                if access_token:
                    # 사용자 OAuth 토큰이 있는 경우 mutual guild만 노출
                    try:
                        user_guild_res = await client.get(
                            f"{DiscordAuthService.DISCORD_API_URL}/users/@me/guilds",
                            headers={"Authorization": f"Bearer {access_token}"},
                        )
                        user_guild_res.raise_for_status()
                        user_guilds = user_guild_res.json()
                        user_guild_ids = {str(g.get("id")) for g in user_guilds if g.get("id")}
                    except Exception as e:
                        print(f"사용자 토큰으로 길드 조회 실패 (무시됨): {e}")

                # 봇 길드
                try:
                    bot_guild_res = await client.get(
                        f"{DiscordAuthService.DISCORD_API_URL}/users/@me/guilds",
                        headers={"Authorization": f"Bot {settings.discord_bot_token}"},
                    )
                    bot_guild_res.raise_for_status()
                    bot_guilds = bot_guild_res.json()
                except Exception as e:
                    print(f"봇 토큰으로 길드 조회 실패: {e}")
                    bot_guilds = []

                channels = []
                for guild in bot_guilds:
                    guild_id = str(guild.get("id"))
                    if user_guild_ids is not None and guild_id not in user_guild_ids:
                        continue
                    guild_name = guild.get("name") or guild_id

                    ch_res = await client.get(
                        f"{DiscordAuthService.DISCORD_API_URL}/guilds/{guild_id}/channels",
                        headers={"Authorization": f"Bot {settings.discord_bot_token}"},
                    )
                    if ch_res.status_code >= 400:
                        continue
                    for ch in ch_res.json():
                        # 0=text, 5=announcement
                        if ch.get("type") in (0, 5):
                            channels.append(
                                {
                                    "guild_id": guild_id,
                                    "guild_name": guild_name,
                                    "channel_id": str(ch.get("id")),
                                    "channel_name": ch.get("name") or str(ch.get("id")),
                                }
                            )

                # 현재 선택된 채널 정보
                columns = DiscordAuthService._get_table_columns("notification_settings")
                where_clause = "user_email=%s" if "user_email" in columns else "user_id=%s"
                selected_channel_id = None
                selected_guild_id = None
                ch_ids = []
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    fields = []
                    if "discord_channel_id" in columns:
                        fields.append("discord_channel_id")
                    elif "channel_id" in columns:
                        fields.append("channel_id")
                    if "discord_guild_id" in columns:
                        fields.append("discord_guild_id")
                    if fields:
                        cursor.execute(
                            f"SELECT {', '.join(fields)} FROM notification_settings WHERE {where_clause} ORDER BY id DESC LIMIT 1",
                            (user_email,),
                        )
                        row = cursor.fetchone()
                        if row:
                            selected_channel_id = row[0] if len(row) >= 1 else None
                            selected_guild_id = row[1] if len(row) >= 2 else None
                            
                            if selected_channel_id:
                                try:
                                    parsed = json.loads(selected_channel_id)
                                    ch_ids = parsed if isinstance(parsed, list) else [str(selected_channel_id)]
                                except:
                                    ch_ids = [str(selected_channel_id)]
                finally:
                    conn.close()

                return {
                    "ok": True,
                    "channels": channels,
                    "discord_channel_ids": ch_ids,
                    "selected_channel_id": ch_ids[0] if ch_ids else None,
                    "selected_guild_id": selected_guild_id,
                }
        except Exception as e:
            return {"ok": False, "message": "채널 목록 조회 실패", "error": str(e)}

    @staticmethod
    def set_selected_channel(user_email: str, guild_id: str, channel_id: Union[str, List[str]]) -> dict:
        try:
            # 리스트일 경우 JSON 문자열로 변환
            db_channel_id = channel_id
            if isinstance(channel_id, list):
                db_channel_id = json.dumps(channel_id)
            
            columns = DiscordAuthService._get_table_columns("notification_settings")
            where_clause = "user_email=%s" if "user_email" in columns else "user_id=%s"
            update_parts = []
            params = []

            if "discord_channel_id" in columns:
                update_parts.append("discord_channel_id=%s")
                params.append(db_channel_id)
            if "discord_guild_id" in columns:
                update_parts.append("discord_guild_id=%s")
                params.append(guild_id)
            if "channel_id" in columns:
                update_parts.append("channel_id=%s")
                params.append(db_channel_id)
            if "discord_webhook_url" in columns:
                update_parts.append("discord_webhook_url=%s")
                params.append("")  # 채널을 직접 선택하면 기존 웹훅은 초기화
            if "webhook_url" in columns:
                update_parts.append("webhook_url=%s")
                params.append("")
            if "updated_at" in columns:
                update_parts.append("updated_at=CURRENT_TIMESTAMP")

            if not update_parts:
                return {"ok": False, "message": "채널 정보를 저장할 컬럼이 없습니다"}

            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE notification_settings SET {', '.join(update_parts)} WHERE {where_clause}",
                    tuple(params + [user_email]),
                )
                conn.commit()
            finally:
                conn.close()

            return {"ok": True, "channel_id": channel_id, "guild_id": guild_id}
        except Exception as e:
            return {"ok": False, "message": "채널 선택 저장 실패", "error": str(e)}
    
    @staticmethod
    def get_oauth_url(state: str = "") -> str:
        """
        Discord OAuth URL 생성
        프론트에서 이 URL로 사용자를 리다이렉트
        """
        if not settings.discord_client_id:
            raise RuntimeError("DISCORD_CLIENT_ID 설정이 필요합니다")
        if not settings.discord_oauth_redirect_uri:
            raise RuntimeError("DISCORD_OAUTH_REDIRECT_URI 설정이 필요합니다")

        params = {
            "client_id": settings.discord_client_id,
            "redirect_uri": settings.discord_oauth_redirect_uri,
            "response_type": "code",
            # Discord OAuth 팝업에서 서버/채널을 선택하도록 webhook.incoming 사용
            "scope": "identify guilds bot",
            "permissions": 2048,
            "state": state or "ppa_oauth"
        }
        from urllib.parse import urlencode
        query_string = urlencode(params)
        return f"{DiscordAuthService.DISCORD_OAUTH_URL}?{query_string}"
    
    @staticmethod
    async def handle_oauth_callback(code: str, user_email: str) -> dict:
        """
        OAuth callback에서 받은 code를 access_token으로 교환
        DB에 저장 후 반환
        """
        try:
            async with httpx.AsyncClient() as client:
                # 토큰 교환
                token_response = await client.post(
                    DiscordAuthService.DISCORD_TOKEN_URL,
                    data={
                        "client_id": settings.discord_client_id,
                        "client_secret": settings.discord_client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": settings.discord_oauth_redirect_uri,
                        "scope": "identify webhook.incoming"
                    }
                )
                token_response.raise_for_status()
                token_data = token_response.json()
                
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 604800)  # 7 days default
                
                # 사용자 정보 조회
                user_response = await client.get(
                    f"{DiscordAuthService.DISCORD_API_URL}/users/@me",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                
                discord_user_id = user_data.get("id")
                discord_username = user_data.get("username")
                webhook = token_data.get("webhook") or {}
                webhook_url = webhook.get("url")
                webhook_channel_id = str(webhook.get("channel_id")) if webhook.get("channel_id") else None
                webhook_guild_id = str(webhook.get("guild_id")) if webhook.get("guild_id") else None
                
                # DB에 저장
                conn = get_connection()
                cursor = conn.cursor()
                
                token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                columns = DiscordAuthService._get_table_columns("notification_settings")
                insert_columns = []
                insert_values = []
                update_parts = []

                def add_column(column_name: str, value):
                    if column_name in columns:
                        insert_columns.append(column_name)
                        insert_values.append(value)

                def default_for(column_name: str):
                    if column_name in {"channel_id", "discord_channel_id", "discord_webhook_url"}:
                        return ""
                    if column_name in {"webhook_url"}:
                        return ""
                    if column_name in {"keywords", "sources"}:
                        return "[]"
                    if column_name in {"language"}:
                        return "all"
                    if column_name in {"summary_length"}:
                        return "medium"
                    if column_name in {"frequency"}:
                        return "daily"
                    if column_name in {"is_active"}:
                        return False
                    return None

                # 구/신 스키마 모두 대응
                add_column("user_email", user_email)
                add_column("user_id", user_email)
                add_column("notification_channel", "discord")
                add_column("channel_id", webhook_channel_id or default_for("channel_id"))
                add_column("webhook_url", default_for("webhook_url"))
                add_column("discord_user_id", discord_user_id)
                add_column("discord_username", discord_username)
                add_column("discord_guild_id", webhook_guild_id)
                add_column("discord_channel_id", webhook_channel_id or default_for("discord_channel_id"))
                add_column("discord_webhook_url", webhook_url or default_for("discord_webhook_url"))
                add_column("discord_access_token", access_token)
                add_column("discord_refresh_token", refresh_token)
                add_column("discord_token_expires_at", token_expires_at)
                add_column("last_discord_test_status", None)
                add_column("last_discord_test_at", None)
                add_column("is_active", False)
                add_column("frequency", default_for("frequency"))
                add_column("keywords", default_for("keywords"))
                add_column("sources", default_for("sources"))
                add_column("language", default_for("language"))
                add_column("summary_length", default_for("summary_length"))

                if not insert_columns:
                    raise RuntimeError("notification_settings 테이블을 저장할 수 있는 컬럼이 없습니다")

                if "discord_user_id" in columns:
                    update_parts.extend([
                        "discord_user_id=VALUES(discord_user_id)",
                        "discord_username=VALUES(discord_username)",
                        "discord_channel_id=VALUES(discord_channel_id)",
                        "discord_guild_id=VALUES(discord_guild_id)",
                        "discord_webhook_url=VALUES(discord_webhook_url)",
                        "discord_access_token=VALUES(discord_access_token)",
                        "discord_refresh_token=VALUES(discord_refresh_token)",
                        "discord_token_expires_at=VALUES(discord_token_expires_at)",
                        "updated_at=CURRENT_TIMESTAMP",
                    ])
                if "channel_id" in columns:
                    update_parts.append("channel_id=VALUES(channel_id)")
                if "user_email" in columns or "user_id" in columns:
                    update_parts.append("updated_at=CURRENT_TIMESTAMP")

                insert_sql = f"INSERT INTO notification_settings ({', '.join(insert_columns)}) VALUES ({', '.join(['%s'] * len(insert_columns))})"
                if update_parts:
                    insert_sql += f" ON DUPLICATE KEY UPDATE {', '.join(update_parts)}"
                
                cursor.execute(insert_sql, tuple(insert_values))
                conn.commit()
                conn.close()
                
                return {
                    "ok": True,
                    "discord_user_id": discord_user_id,
                    "discord_username": discord_username,
                    "expires_in": expires_in,
                    "message": "Discord 연결 성공"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "Discord OAuth 처리 실패"
            }
    
    @staticmethod
    def get_connection_status(user_email: str) -> dict:
        """
        사용자의 Discord 연결 상태 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            columns = DiscordAuthService._get_table_columns("notification_settings")

            id_filter = "user_email = %s" if "user_email" in columns else "user_id = %s"
            connected_sql = ["id"]
            for column_name in [
                "discord_user_id",
                "discord_username",
                "discord_channel_id",
                "discord_guild_id",
                "last_discord_test_status",
                "last_discord_test_at",
                "is_active",
                "notification_channel",
                "channel_id",
            ]:
                if column_name in columns:
                    connected_sql.append(column_name)
            
            cursor.execute("""
                SELECT {fields}
                FROM notification_settings
                WHERE {id_filter}
                ORDER BY id DESC
                LIMIT 1
            """.format(fields=", ".join(connected_sql), id_filter=id_filter), (user_email,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                connected = bool(result.get("discord_user_id")) or result.get("notification_channel") == "discord" or bool(result.get("channel_id"))
                return {
                    "ok": True,
                    "connected": connected,
                    "discord_username": result.get("discord_username"),
                    "discord_channel_id": result.get("discord_channel_id"),
                    "discord_guild_id": result.get("discord_guild_id"),
                    "last_test_status": result.get("last_discord_test_status"),
                    "last_test_at": int(result.get("last_discord_test_at").timestamp()) if result.get("last_discord_test_at") else None,
                    "is_active": bool(result.get("is_active"))
                }
            else:
                return {
                    "ok": True,
                    "connected": False,
                    "message": "아직 Discord가 연결되지 않음"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "상태 조회 실패"
            }
    
    @staticmethod
    async def refresh_access_token(refresh_token: str) -> dict:
        """
        만료된 access_token을 refresh_token으로 갱신
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    DiscordAuthService.DISCORD_TOKEN_URL,
                    data={
                        "client_id": settings.discord_client_id,
                        "client_secret": settings.discord_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                response.raise_for_status()
                token_data = response.json()
                
                return {
                    "ok": True,
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_in": token_data.get("expires_in")
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "토큰 갱신 실패"
            }
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            columns = DiscordAuthService._get_table_columns("notification_settings")

            id_filter = "user_email = %s" if "user_email" in columns else "user_id = %s"
            connected_sql = ["id"]
            for column_name in [
                "discord_user_id",
                "discord_username",
                "discord_channel_id",
                "discord_guild_id",
                "last_discord_test_status",
                "last_discord_test_at",
                "is_active",
                "notification_channel",
                "channel_id",
            ]:
                if column_name in columns:
                    connected_sql.append(column_name)
            
            cursor.execute("""
                SELECT {fields}
                FROM notification_settings
                WHERE {id_filter}
                ORDER BY id DESC
                LIMIT 1
            """.format(fields=", ".join(connected_sql), id_filter=id_filter), (user_email,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # channel_id 파싱 (JSON 리스트)
                raw_ch = result.get("channel_id")
                ch_ids = []
                if raw_ch:
                    try:
                        parsed = json.loads(raw_ch)
                        ch_ids = parsed if isinstance(parsed, list) else [str(raw_ch)]
                    except:
                        ch_ids = [str(raw_ch)]

                connected = bool(result.get("discord_user_id")) or result.get("notification_channel") == "discord" or len(ch_ids) > 0
                return {
                    "ok": True,
                    "connected": connected,
                    "discord_username": result.get("discord_username"),
                    "discord_channel_id": ch_ids[0] if ch_ids else None,
                    "discord_channel_ids": ch_ids,
                    "discord_guild_id": result.get("discord_guild_id"),
                    "last_test_status": result.get("last_discord_test_status"),
                    "last_test_at": int(result.get("last_discord_test_at").timestamp()) if result.get("last_discord_test_at") else None,
                    "is_active": bool(result.get("is_active"))
                }
            else:
                return {
                    "ok": True,
                    "connected": False,
                    "message": "아직 Discord가 연결되지 않음"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "상태 조회 실패"
            }
    
    @staticmethod
    async def refresh_access_token(refresh_token: str) -> dict:
        """
        만료된 access_token을 refresh_token으로 갱신
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    DiscordAuthService.DISCORD_TOKEN_URL,
                    data={
                        "client_id": settings.discord_client_id,
                        "client_secret": settings.discord_client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                response.raise_for_status()
                token_data = response.json()
                
                return {
                    "ok": True,
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_in": token_data.get("expires_in")
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "토큰 갱신 실패"
            }
