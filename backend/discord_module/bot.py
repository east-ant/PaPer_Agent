import discord
from discord.ext import commands
import asyncio
import os
import logging
from storage_box.service import StorageBoxService

logger = logging.getLogger(__name__)

class PaperBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        print("[Bot] Discord Gateway connecting...")

    async def on_ready(self):
        print(f"[Bot] Login complete: {self.user.name} ({self.user.id})")

    async def on_interaction(self, interaction: discord.Interaction):
        # 버튼 클릭 처리 (Component Interaction)
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            print(f"[Bot] Button click received: {custom_id} (User: {interaction.user.id})")
            
            if custom_id.startswith("save:"):
                await interaction.response.defer(ephemeral=True)
                
                parts = custom_id.split(":", 2)
                if len(parts) >= 2:
                    paper_idx_str = parts[1]
                    
                    try:
                        # 1) 디스코드 유저 ID로 이메일 조회
                        from database import get_connection
                        import pymysql
                        conn = get_connection()
                        cursor = conn.cursor(pymysql.cursors.DictCursor)
                        
                        cursor.execute("""
                            SELECT user_email FROM notification_settings 
                            WHERE discord_user_id = %s OR channel_id = %s
                            ORDER BY id DESC LIMIT 1
                        """, (str(interaction.user.id), str(interaction.channel_id)))
                        
                        user_info = cursor.fetchone()
                        conn.close()
                        
                        if not user_info:
                            await interaction.followup.send("❌ 이 채널에 연결된 사용자 정보를 찾을 수 없습니다. 웹사이트에서 디스코드 연결을 먼저 완료해주세요.", ephemeral=True)
                            return
                        
                        user_email = user_info["user_email"]
                        
                        # 2) 메시지 Embed에서 논문 정보 추출
                        paper_idx = int(paper_idx_str)
                        if paper_idx < len(interaction.message.embeds):
                            embed = interaction.message.embeds[paper_idx]
                            # 제목에서 "1. " 형태의 말머리 제거
                            title = embed.title if embed.title else "제목 없음"
                            import re
                            title = re.sub(r'^\d+\.\s*', '', title)
                            
                            summary = embed.description if embed.description else ""
                            link = embed.url if embed.url else ""
                            source = "discord_bot"
                            
                            if embed.fields:
                                for field in embed.fields:
                                    if field.name == "출처":
                                        source = field.value
                                        break
                            
                            # 아카이브 ID 추출 시도 (url에서)
                            paper_id = ""
                            if "arxiv.org/abs/" in link:
                                paper_id = link.split("arxiv.org/abs/")[-1]
                            else:
                                paper_id = link
                            
                            # 3) 보관함에 저장
                            result = StorageBoxService.save_bookmark(user_email, {
                                "id": paper_id,
                                "paper_id": paper_id,
                                "title": title,
                                "summary": summary,
                                "link": link,
                                "source": source
                            })
                        
                        if result.get("ok"):
                            await interaction.followup.send("✅ 논문이 보관함에 저장되었습니다!", ephemeral=True)
                        else:
                            await interaction.followup.send(f"❌ 저장 실패: {result.get('message')}", ephemeral=True)
                    except Exception as e:
                        await interaction.followup.send(f"❌ 오류 발생: {str(e)}", ephemeral=True)

# 싱글톤 봇 인스턴스
bot = PaperBot()

async def start_bot():
    # 환경 변수에서 토큰 가져오기 (DISCORD_TOKEN 우선)
    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    
    if not token:
        print("[Bot] DISCORD_TOKEN not set. Cannot start bot.")
        return
    
    print(f"[Bot] Discord Gateway connection attempt... (Token: {token[:10]}***)")
    try:
        await bot.start(token)
    except Exception as e:
        print(f"[Bot] Start failed: {e}")

def run_bot_in_background():
    try:
        # 이미 루프가 실행 중인 경우 태스크 추가
        loop = asyncio.get_running_loop()
        loop.create_task(start_bot())
        print("[Bot] Background task registered")
    except RuntimeError:
        # 루프가 없는 경우 (보통 발생하지 않음)
        print("[Bot] Event loop not found")
