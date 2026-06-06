# Discord Notifications - Discord API 연동
import httpx
from typing import List
from config import settings

class DiscordNotificationService:
    """
    Discord 메시지 발송 서비스
    """
    
    @staticmethod
    async def send_test_message(webhook_url: str) -> dict:
        """
        테스트 메시지 발송 (Webhook 이용)
        """
        try:
            embed_data = {
                "title": "🧪 테스트 알림",
                "description": "Paper Agent Discord 연동이 성공적으로 완료되었습니다!",
                "color": 0x00ff00,
                "fields": [
                    {
                        "name": "상태",
                        "value": "정상 작동",
                        "inline": True
                    },
                    {
                        "name": "시간",
                        "value": "정상",
                        "inline": True
                    }
                ]
            }
            
            payload = {
                "embeds": [embed_data]
            }
            
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code == 204:  # Webhook 성공 응답
                    return {
                        "ok": True,
                        "message": "테스트 메시지 발송 완료"
                    }
                else:
                    body = response.text[:500] if response.text else ""
                    return {
                        "ok": False,
                        "error": f"HTTP {response.status_code}",
                        "message": f"메시지 발송 실패: {body}" if body else "메시지 발송 실패"
                    }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "테스트 발송 중 오류 발생"
            }

    @staticmethod
    async def send_test_message_to_channel(channel_id: str) -> dict:
        """
        테스트 메시지 발송 (Bot Token + Channel ID)
        """
        bot_token = settings.discord_bot_token
        if not bot_token:
            return {
                "ok": False,
                "message": "DISCORD_BOT_TOKEN 설정이 필요합니다"
            }
        if not channel_id:
            return {
                "ok": False,
                "message": "채널을 먼저 선택해주세요"
            }

        payload = {
            "content": "🧪 Paper Agent 테스트 알림입니다. 연결이 정상 동작합니다!"
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers={
                        "Authorization": f"Bot {bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code in (200, 201):
                    return {
                        "ok": True,
                        "message": "테스트 메시지 발송 완료"
                    }

                body = response.text
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "message": f"메시지 발송 실패: {body}"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "테스트 발송 중 오류 발생"
            }
    
    @staticmethod
    async def send_papers(webhook_url: str, papers: List[dict], 
                         user_email: str = None) -> dict:
        """
        논문 목록을 Discord Embed로 발송 (Webhook 이용)
        """
        try:
            if not webhook_url:
                return {"ok": False, "error": "Webhook URL이 없습니다."}

            if not papers:
                embed_data = {
                    "title": "📰 논문 검색 결과",
                    "description": "해당하는 논문이 없습니다",
                    "color": 0xffa500
                }
                payload = {"embeds": [embed_data]}
            else:
                embeds = []
                buttons = []
                for i, paper in enumerate(papers[:10]):
                    embed = DiscordNotificationService._create_paper_embed(paper, i + 1, user_email=user_email)
                    embeds.append(embed)
                    if "_save_button" in paper:
                        btn = paper["_save_button"]
                        btn["label"] = f"📥 #{i+1} 저장"
                        buttons.append(btn)
                
                summary_embed = {
                    "title": f"논문 검색 결과 ({len(papers)}개)",
                    "description": f"{len(papers)}개의 새로운 논문을 발견했습니다!",
                    "color": 0x0099ff,
                    "footer": {
                        "text": "Paper Agent 자동 수집"
                    }
                }
                embeds.insert(0, summary_embed)
                
                # 버튼을 Action Rows로 나누기 (최대 5개씩 한 줄)
                components = []
                if buttons:
                    for i in range(0, min(len(buttons), 25), 5):
                        components.append({
                            "type": 1,
                            "components": buttons[i:i+5]
                        })
                
                payload = {
                    "embeds": embeds[:10],
                    "components": components[:5]
                }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload)
                
                if response.status_code == 204:
                    return {
                        "ok": True,
                        "papers_count": len(papers),
                        "message": f"{len(papers)}개 논문 발송 완료"
                    }
                else:
                    return {
                        "ok": False,
                        "error": f"HTTP {response.status_code}",
                        "message": "논문 발송 실패"
                    }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "논문 발송 중 오류 발생"
            }

    @staticmethod
    async def send_papers_to_channel(channel_id: str, papers: List[dict], 
                                    user_email: str = None) -> dict:
        """
        논문 목록을 Discord Embed로 발송 (Bot Token + Channel ID 이용)
        """
        bot_token = settings.discord_bot_token
        if not bot_token:
            return {"ok": False, "message": "DISCORD_BOT_TOKEN 설정이 필요합니다"}
        
        try:
            if not papers:
                embeds = [{
                    "title": "📰 논문 검색 결과",
                    "description": "해당하는 논문이 없습니다",
                    "color": 0xffa500
                }]
            else:
                embeds = []
                buttons = []
                for i, paper in enumerate(papers[:10]):
                    embed = DiscordNotificationService._create_paper_embed(paper, i + 1, user_email=user_email)
                    embeds.append(embed)
                    if "_save_button" in paper:
                        btn = paper["_save_button"]
                        btn["label"] = f"📥 #{i+1} 저장"
                        buttons.append(btn)
                
                summary_embed = {
                    "title": f"논문 검색 결과 ({len(papers)}개)",
                    "description": f"{len(papers)}개의 새로운 논문을 발견했습니다!",
                    "color": 0x0099ff,
                    "footer": {
                        "text": "Paper Agent 자동 수집"
                    }
                }
                embeds.insert(0, summary_embed)
            
            # 버튼을 Action Rows로 나누기
            components = []
            if buttons:
                for i in range(0, min(len(buttons), 25), 5):
                    components.append({
                        "type": 1,
                        "components": buttons[i:i+5]
                    })
            
            payload = {
                "embeds": embeds[:10],
                "components": components[:5]
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers={
                        "Authorization": f"Bot {bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if response.status_code in (200, 201):
                    return {
                        "ok": True,
                        "papers_count": len(papers),
                        "message": f"{len(papers)}개 논문 발송 완료"
                    }

                body = response.text
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "message": f"메시지 발송 실패: {body}"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "논문 발송 중 오류 발생"
            }
    
    @staticmethod
    def _create_paper_embed(paper: dict, index: int = 1, user_email: str = None) -> dict:
        """
        논문 정보를 Discord Embed 형식으로 변환
        """
        import os
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        
        title = paper.get("title", "제목 없음")[:256]
        authors = paper.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(authors[:3])
        else:
            authors_str = str(authors)[:200]
        
        summary_to_show = paper.get("abstract_ko") or paper.get("summary") or paper.get("abstract", "요약 없음")
        # Discord Embed description 최대 길이는 4096자이므로 4000자로 여유 있게 자름
        summary = summary_to_show[:4000]
        
        link = paper.get("link", "") or paper.get("url", "")
        source = paper.get("source", "Unknown")
        published = paper.get("published") or paper.get("year") or paper.get("published_date") or "Unknown"
        
        citations = paper.get("citationCount") or paper.get("citations") or 0
        
        embed = {
            "title": f"{index}. {title}",
            "description": summary + ("..." if len(summary_to_show) > 4000 else ""),
            "url": link if link else None,
            "color": 0x6366f1,
            "fields": [
                {
                    "name": "저자",
                    "value": authors_str if authors_str else "저자 정보 없음",
                    "inline": True
                },
                {
                    "name": "인용 수",
                    "value": f"{citations}회" if citations else "0회",
                    "inline": True
                },
                {
                    "name": "\u200b",
                    "value": "\u200b",
                    "inline": False
                },
                {
                    "name": "출처",
                    "value": source,
                    "inline": True
                },
                {
                    "name": "발행일",
                    "value": str(published)[:10],
                    "inline": True
                }
            ]
        }
        
        if user_email and link:
            # custom_id: "save:<index>:<user_email>" 형식
            custom_id = f"save:{index}:{user_email}"
            
            # Interaction Button (style 1 = Primary 파란 버튼)
            paper["_save_button"] = {
                "type": 2,
                "style": 1,  # Primary (파란 버튼)
                "label": "📥 보관함에 저장",
                "custom_id": custom_id
            }
        
        return embed
