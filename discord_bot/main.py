import asyncio
import base64
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Literal
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

try:
    from discord_bot.bot import bot, send_alert, start_bot
except ImportError:
    from bot import bot, send_alert, start_bot

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALERTS_PATH = os.path.join(BASE_DIR, "alerts.json")
AUTO_ALERTS_PATH = os.path.join(BASE_DIR, "auto_alerts.json")
PAPER_HOME_PATH = os.path.join(BASE_DIR, "paper_home.json")
load_dotenv(str(Path(BASE_DIR) / ".env"), override=True)

scheduler = AsyncIOScheduler()
_bot_thread_started = False
oauth_sessions: dict[str, dict] = {}


DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_OAUTH_REDIRECT_URI = os.getenv("DISCORD_OAUTH_REDIRECT_URI", "")
DISCORD_OAUTH_STATE_SECRET = os.getenv("DISCORD_OAUTH_STATE_SECRET", DISCORD_CLIENT_SECRET or "paperinform_state_secret")
DISCORD_OAUTH_STATE_TTL_SECONDS = int(os.getenv("DISCORD_OAUTH_STATE_TTL_SECONDS", "900"))
ALERT_API_PORT = os.getenv("ALERT_API_PORT", "8000")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.path.exists(ALERTS_PATH):
        save_alerts([])
    if not os.path.exists(AUTO_ALERTS_PATH):
        save_auto_alerts([])
    if not os.path.exists(PAPER_HOME_PATH):
        save_paper_home([])
    if not scheduler.running:
        scheduler.add_job(scheduled_alert_tick, "cron", minute="*")
        scheduler.start()
    _start_bot_thread_if_needed()

    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_alerts():
    try:
        with open(ALERTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_alerts(data):
    with open(ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_auto_alerts():
    try:
        with open(AUTO_ALERTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_auto_alerts(data):
    with open(AUTO_ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_paper_home() -> list[dict]:
    try:
        with open(PAPER_HOME_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("papers"), list):
            return data.get("papers", [])
        return []
    except Exception:
        return []


def save_paper_home(data: list[dict]):
    with open(PAPER_HOME_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class AlertRequest(BaseModel):
    channel_id: int
    keywords: List[str]
    include_summary: bool = False
    include_category: bool = False


class AlertPreferenceRequest(BaseModel):
    keywords: List[str]
    include_summary: bool = False
    include_category: bool = False
    alert_mode: Literal["daily", "once_now"] = "daily"
    daily_time: str = "09:00"
    discord_user_id: str | None = None


class BotChannelRegisterRequest(BaseModel):
    guild_id: str | int
    channel_id: str | int


class SendNowRequest(BaseModel):
    alert_id: str | None = None


class BindChannelRequest(BaseModel):
    alert_id: str
    guild_id: str | int
    channel_id: str | int


class OAuthLoginUrlRequest(BaseModel):
    redirect_back: str


def _normalize_daily_time(value: str) -> tuple[str, int, int]:
    text = (value or "09:00").strip()
    try:
        hh, mm = text.split(":", 1)
        hour = int(hh)
        minute = int(mm)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return f"{hour:02d}:{minute:02d}", hour, minute
    except Exception:
        return "09:00", 9, 0


def resolve_default_channel_id() -> int | None:
    for guild in bot.guilds:
        me = guild.me
        if me is None:
            continue

        if guild.system_channel and guild.system_channel.permissions_for(me).send_messages:
            return guild.system_channel.id

        for channel in guild.text_channels:
            if channel.permissions_for(me).send_messages:
                return channel.id
    return None


def list_available_channels() -> list[dict]:
    rows = []
    for guild in bot.guilds:
        me = guild.me
        if me is None:
            continue
        for channel in guild.text_channels:
            if channel.permissions_for(me).send_messages:
                rows.append(
                    {
                        "guild_id": str(guild.id),
                        "guild_name": guild.name,
                        "channel_id": str(channel.id),
                        "channel_name": channel.name,
                    }
                )
    return rows


def list_available_channels_for_guilds(allowed_guild_ids: set[str]) -> list[dict]:
    rows = list_available_channels()
    if not allowed_guild_ids:
        return []
    return [row for row in rows if str(row.get("guild_id")) in allowed_guild_ids]


def _require_discord_oauth_env() -> None:
    if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and DISCORD_OAUTH_REDIRECT_URI:
        return
    raise HTTPException(
        status_code=500,
        detail="DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET / DISCORD_OAUTH_REDIRECT_URI 설정이 필요합니다.",
    )


def _exchange_discord_code(code: str) -> dict:
    payload = urllib.parse.urlencode(
        {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://discord.com/api/v10/oauth2/token",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "PaperInformOAuth/1.0 (+http://127.0.0.1)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body_text = ""
        try:
            body_text = error.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        detail = body_text or str(error)
        raise RuntimeError(f"token 교환 실패(status={error.code}): {detail}") from error


def _discord_api_get(path: str, access_token: str) -> dict | list:
    request = urllib.request.Request(
        f"https://discord.com/api/v10{path}",
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "User-Agent": "PaperInformOAuth/1.0 (+http://127.0.0.1)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body_text = ""
        try:
            body_text = error.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        detail = body_text or str(error)
        raise RuntimeError(f"Discord API GET 실패(path={path}, status={error.code}): {detail}") from error


def _build_signed_state(redirect_back: str) -> str:
    payload = {
        "redirect_back": redirect_back,
        "ts": int(time.time()),
    }
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")
    signature = hmac.new(
        DISCORD_OAUTH_STATE_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _parse_signed_state(state: str) -> str:
    try:
        payload_b64, signature = state.split(".", 1)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="state 형식이 올바르지 않습니다.") from error

    expected_signature = hmac.new(
        DISCORD_OAUTH_STATE_SECRET.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=400, detail="state 서명이 유효하지 않습니다.")

    padded = payload_b64 + "=" * (-len(payload_b64) % 4)
    try:
        payload_json = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        payload = json.loads(payload_json)
    except Exception as error:
        raise HTTPException(status_code=400, detail="state 디코딩에 실패했습니다.") from error

    ts = int(payload.get("ts", 0))
    if ts <= 0 or int(time.time()) - ts > DISCORD_OAUTH_STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="state 유효 시간이 지났습니다. 다시 로그인해 주세요.")

    redirect_back = str(payload.get("redirect_back", "")).strip()
    if not redirect_back:
        raise HTTPException(status_code=400, detail="state에 redirect_back 정보가 없습니다.")

    return redirect_back


async def dispatch_discord_alert(**kwargs):
    if not bot.is_ready():
        print("봇이 아직 준비되지 않아 알림 전송을 건너뜁니다.")
        return

    future = asyncio.run_coroutine_threadsafe(send_alert(**kwargs), bot.loop)
    await asyncio.wrap_future(future)


def _sample_papers() -> list[dict]:
    rows = load_paper_home()
    if rows:
        return rows
    return []


def update_profile_channel(alert_id: str, guild_id: int | None, channel_id: int | None, status: str | None = None):
    alerts = load_alerts()
    updated = False
    for row in alerts:
        if row.get("alert_id") == alert_id:
            row["guild_id"] = guild_id
            row["channel_id"] = channel_id
            if status is not None:
                row["status"] = status
            updated = True
            break
    if updated:
        save_alerts(alerts)


def _should_send(alert: dict, now: datetime, ignore_schedule: bool) -> bool:
    if alert.get("status") not in {"active", "pending_discord_install", "done_once"}:
        return False

    if ignore_schedule:
        return True

    mode = alert.get("alert_mode", "daily")
    if mode == "once_now":
        return not bool(alert.get("once_sent", False))

    daily_time, hour, minute = _normalize_daily_time(alert.get("daily_time", "09:00"))
    alert["daily_time"] = daily_time
    if now.hour != hour or now.minute != minute:
        return False

    return alert.get("last_sent_date") != now.date().isoformat()


async def run_alert_dispatch(ignore_schedule: bool, force_alert_id: str | None = None) -> int:
    alerts = load_auto_alerts()
    now = datetime.now()
    papers = _sample_papers()
    sent = 0
    updated = False

    for alert in alerts:
        if force_alert_id and alert.get("alert_id") != force_alert_id:
            continue

        if not _should_send(alert, now, ignore_schedule):
            continue

        if alert.get("enabled", True) is False:
            continue

        channel_id = alert.get("channel_id")
        # 명시적으로 바인딩된 채널이 없으면 발송하지 않는다.
        if not channel_id:
            alert["status"] = "pending_discord_install"
            updated = True
            continue

        try:
            channel_id_int = int(channel_id)
        except (TypeError, ValueError):
            alert["status"] = "pending_discord_install"
            updated = True
            continue

        matched = False
        alert_keywords = {str(k).strip().lower() for k in alert.get("keywords", []) if str(k).strip()}
        for paper in papers:
            paper_keywords = {str(k).strip().lower() for k in paper.get("keywords", []) if str(k).strip()}
            if alert_keywords & paper_keywords:
                await dispatch_discord_alert(
                    channel_id=channel_id_int,
                    title=paper["title"],
                    link=paper["link"],
                    summary=paper.get("summary"),
                    category=paper.get("category"),
                    include_summary=alert.get("include_summary", False),
                    include_category=alert.get("include_category", False),
                )
                matched = True
                sent += 1
                break

        if matched:
            alert["last_sent_at"] = now.isoformat(timespec="seconds")
            if alert.get("alert_mode", "daily") == "once_now":
                alert["once_sent"] = True
                alert["status"] = "done_once"
                update_profile_channel(alert.get("alert_id"), alert.get("guild_id"), alert.get("channel_id"), "done_once")
            else:
                alert["last_sent_date"] = now.date().isoformat()
                alert["status"] = "active"
                update_profile_channel(alert.get("alert_id"), alert.get("guild_id"), alert.get("channel_id"), "active")
            updated = True

    if updated:
        save_auto_alerts(alerts)

    return sent


@app.post("/api/alerts")
async def save_alert(req: AlertRequest):
    alerts = load_alerts()
    alerts.append(
        {
            "alert_id": str(uuid4()),
            "guild_id": None,
            "channel_id": req.channel_id,
            "keywords": req.keywords,
            "include_summary": req.include_summary,
            "include_category": req.include_category,
            "alert_mode": "daily",
            "daily_time": "09:00",
            "once_sent": False,
            "status": "active",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_alerts(alerts)
    return {"status": "저장 완료"}


@app.post("/api/auth/discord/login-url")
async def create_discord_login_url(req: OAuthLoginUrlRequest):
    _require_discord_oauth_env()

    state = _build_signed_state(req.redirect_back)
    params = urllib.parse.urlencode(
        {
            "client_id": DISCORD_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
            "scope": "identify guilds",
            "state": state,
            "prompt": "consent",
        }
    )
    return {"url": f"https://discord.com/api/oauth2/authorize?{params}"}


@app.get("/api/auth/discord/callback")
async def discord_oauth_callback(code: str = Query(default=""), state: str = Query(default="")):
    _require_discord_oauth_env()
    redirect_back = _parse_signed_state(state)
    if not code:
        raise HTTPException(status_code=400, detail="code 값이 없습니다.")

    try:
        token_data = _exchange_discord_code(code)
        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("access_token이 없습니다")
        user = _discord_api_get("/users/@me", access_token)
        guilds = _discord_api_get("/users/@me/guilds", access_token)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Discord OAuth 처리 실패: {error}")

    session_id = str(uuid4())
    oauth_sessions[session_id] = {
        "user": user,
        "guild_ids": {str(g.get("id")) for g in guilds if isinstance(g, dict)},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    separator = "&" if "?" in redirect_back else "?"
    target = f"{redirect_back}{separator}auth_session={session_id}&api=http://127.0.0.1:{ALERT_API_PORT}"
    return RedirectResponse(url=target, status_code=302)


@app.get("/api/auth/session/{session_id}")
async def get_oauth_session(session_id: str):
    session = oauth_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션이 없습니다. 다시 로그인해 주세요.")
    user = session.get("user", {})
    return {
        "session_id": session_id,
        "user": {
            "id": str(user.get("id", "")),
            "username": user.get("username"),
            "global_name": user.get("global_name"),
        },
        "guild_count": len(session.get("guild_ids", set())),
    }


@app.get("/api/auth/discord/debug-config")
async def debug_discord_oauth_config():
    return {
        "client_id_set": bool(DISCORD_CLIENT_ID),
        "client_secret_set": bool(DISCORD_CLIENT_SECRET),
        "redirect_uri": DISCORD_OAUTH_REDIRECT_URI,
        "alert_api_port": ALERT_API_PORT,
    }


@app.post("/api/alert-preferences")
async def save_alert_preference(req: AlertPreferenceRequest):
    alerts = load_alerts()
    auto_alerts = load_auto_alerts()
    normalized_time, _, _ = _normalize_daily_time(req.daily_time)
    alert_id = str(uuid4())

    alerts.append(
        {
            "alert_id": alert_id,
            "discord_user_id": req.discord_user_id,
            "guild_id": None,
            "channel_id": None,
            "status": "pending_discord_install",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )

    auto_alerts.append(
        {
            "alert_id": alert_id,
            "discord_user_id": req.discord_user_id,
            "guild_id": None,
            "channel_id": None,
            "keywords": req.keywords,
            "include_summary": req.include_summary,
            "include_category": req.include_category,
            "alert_mode": req.alert_mode,
            "daily_time": normalized_time,
            "enabled": True,
            "once_sent": False,
            "last_sent_date": None,
            "last_sent_at": None,
            "status": "pending_discord_install",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_alerts(alerts)
    save_auto_alerts(auto_alerts)

    # 채널 바인딩 전에는 즉시 발송하지 않는다.
    return {"status": "설정 저장 완료", "alert_id": alert_id, "sent_now": 0}


@app.post("/api/bot/channel-register")
async def register_bot_channel(req: BotChannelRegisterRequest):
    guild_id = str(req.guild_id)
    channel_id = str(req.channel_id)
    alerts = load_auto_alerts()
    updated = 0
    matched_alert_id = None

    for alert in reversed(alerts):
        if alert.get("status") == "pending_discord_install" and not alert.get("channel_id"):
            alert["guild_id"] = guild_id
            alert["channel_id"] = channel_id
            if alert.get("alert_mode", "daily") == "once_now" and alert.get("once_sent", False):
                alert["status"] = "done_once"
            else:
                alert["status"] = "active"
            updated += 1
            matched_alert_id = alert.get("alert_id")
            update_profile_channel(matched_alert_id, guild_id, channel_id, alert.get("status"))
            break

    if updated:
        save_auto_alerts(alerts)

    sent_now = 0
    if matched_alert_id:
        sent_now = await run_alert_dispatch(ignore_schedule=True, force_alert_id=matched_alert_id)
    return {
        "status": "ok",
        "updated": updated,
        "alert_id": matched_alert_id,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "sent_now": sent_now,
    }


@app.get("/api/bot/channels")
async def get_bot_channels(session_id: str | None = None):
    if session_id:
        session = oauth_sessions.get(session_id)
        if not session:
            raise HTTPException(status_code=401, detail="로그인 세션이 만료되었거나 유효하지 않습니다.")
        allowed_guild_ids = session.get("guild_ids", set())
        channels = list_available_channels_for_guilds(set(allowed_guild_ids))
    else:
        channels = list_available_channels()
    return {"count": len(channels), "channels": channels}


@app.post("/api/alerts/bind-channel")
async def bind_alert_channel(req: BindChannelRequest):
    guild_id = str(req.guild_id)
    channel_id = str(req.channel_id)
    alerts = load_alerts()
    auto_alerts = load_auto_alerts()
    updated = False
    auto_updated = False

    for alert in alerts:
        if alert.get("alert_id") == req.alert_id:
            alert["guild_id"] = guild_id
            alert["channel_id"] = channel_id
            if alert.get("alert_mode", "daily") == "once_now" and alert.get("once_sent", False):
                alert["status"] = "done_once"
            else:
                alert["status"] = "active"
            updated = True
            break

    if not updated:
        return {"status": "not_found", "updated": 0}

    save_alerts(alerts)

    for row in auto_alerts:
        if row.get("alert_id") == req.alert_id:
            row["guild_id"] = guild_id
            row["channel_id"] = channel_id
            if row.get("alert_mode", "daily") == "once_now" and row.get("once_sent", False):
                row["status"] = "done_once"
            else:
                row["status"] = "active"
            auto_updated = True
            break

    if auto_updated:
        save_auto_alerts(auto_alerts)

    sent_now = await run_alert_dispatch(ignore_schedule=True, force_alert_id=req.alert_id)
    return {"status": "ok", "updated": 1, "alert_id": req.alert_id, "sent_now": sent_now}


@app.get("/api/alerts")
async def get_alerts():
    alerts = load_alerts()
    return {"count": len(alerts), "alerts": alerts}


@app.get("/api/auto-alerts")
async def get_auto_alerts():
    rows = load_auto_alerts()
    return {"count": len(rows), "alerts": rows}


@app.get("/api/paper-home")
async def get_paper_home():
    rows = load_paper_home()
    return {"count": len(rows), "papers": rows}


@app.post("/api/alerts/send-now")
async def send_now(req: SendNowRequest):
    sent = await run_alert_dispatch(ignore_schedule=True, force_alert_id=req.alert_id)
    return {"status": "ok", "sent": sent}


@app.delete("/api/auto-alerts/{alert_id}")
async def delete_auto_alert(alert_id: str):
    auto_rows = load_auto_alerts()
    profile_rows = load_alerts()

    next_auto_rows = [row for row in auto_rows if row.get("alert_id") != alert_id]
    next_profile_rows = [row for row in profile_rows if row.get("alert_id") != alert_id]

    removed = len(auto_rows) - len(next_auto_rows)
    save_auto_alerts(next_auto_rows)
    save_alerts(next_profile_rows)

    return {"status": "ok", "removed": removed}


async def scheduled_alert_tick():
    await run_alert_dispatch(ignore_schedule=False)


def _start_bot_thread_if_needed():
    global _bot_thread_started
    if _bot_thread_started:
        return
    if not os.getenv("DISCORD_TOKEN"):
        print("DISCORD_TOKEN이 없어 봇 실행은 건너뜁니다. API만 실행합니다.")
        return

    def run_bot():
        start_bot()

    threading.Thread(target=run_bot, daemon=True).start()
    _bot_thread_started = True


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("ALERT_API_PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=port)