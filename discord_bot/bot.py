import discord
from discord.ext import commands
import os
import time
from pathlib import Path
import json
import urllib.request
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(str(BASE_DIR / ".env"), override=True)
TOKEN = os.getenv("DISCORD_TOKEN")
ALERT_API_PORT = os.getenv("ALERT_API_PORT", "8000")
ALERT_API_URL = os.getenv("ALERT_API_URL", f"http://127.0.0.1:{ALERT_API_PORT}")

intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


def pick_default_channel_id(guild: discord.Guild) -> int | None:
    me = guild.me
    if guild.system_channel and guild.system_channel.permissions_for(me).send_messages:
        return guild.system_channel.id

    for channel in guild.text_channels:
        if channel.permissions_for(me).send_messages:
            return channel.id
    return None


def post_channel_registration(guild_id: int, channel_id: int) -> None:
    payload = json.dumps({"guild_id": guild_id, "channel_id": channel_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{ALERT_API_URL}/api/bot/channel-register",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error = None
    for _ in range(8):
        try:
            with urllib.request.urlopen(request, timeout=10):
                return
        except Exception as error:
            last_error = error
            time.sleep(0.5)
    if last_error is not None:
        raise last_error


async def register_guild_channel(guild: discord.Guild) -> None:
    channel_id = pick_default_channel_id(guild)
    if not channel_id:
        print(f"길드 {guild.id} 에서 전송 가능한 채널을 찾지 못했습니다.")
        return

    try:
        await bot.loop.run_in_executor(None, post_channel_registration, guild.id, channel_id)
        print(f"길드 {guild.id} 채널 {channel_id} 등록 완료")
    except Exception as error:
        print(f"채널 등록 실패(guild={guild.id}, channel={channel_id}): {error}")

@bot.event
async def on_ready():
    print(f"{bot.user} 봇 실행 완료!")
    for guild in bot.guilds:
        await register_guild_channel(guild)


@bot.event
async def on_guild_join(guild: discord.Guild):
    await register_guild_channel(guild)

async def send_alert(channel_id: int, title: str, link: str, summary: str = None, category: str = None, include_summary: bool = False, include_category: bool = False):
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"채널 {channel_id} 를 찾을 수 없음.")
        return

    message = f" **{title}**\n {link}"
    
    if include_category and category:
        message += f"\n {category}"
    if include_summary and summary:
        message += f"\n {summary}"

    await channel.send(message)


def start_bot() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set")
    bot.run(TOKEN)