# Notice Scheduler - APScheduler 관리
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
import pymysql
import json
from database import get_connection
from .service import NoticeService
from config import settings
import sys
import os

# api_get 모듈 임포트
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from api_get import remove_duplicates
except ImportError:
    remove_duplicates = None

scheduler = AsyncIOScheduler()

async def send_scheduled_alert(notification_settings_id: int, user_email: str):
    """
    스케줄된 알림 발송 (오후 2시에 실행)
    """
    try:
        # 설정 확인
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # notification_settings와 agent_configs 함께 조회
        cursor.execute("""
            SELECT 
                a.id as agent_id,
                a.keywords,
                a.sources,
                a.collect_count,
                a.language,
                a.summary_length,
                a.is_active,
                n.id as notification_id,
                n.channel_id,
                n.webhook_url
            FROM agent_configs a
            JOIN notification_settings n ON a.user_email = n.user_email
            WHERE n.id = %s
        """, (notification_settings_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            print(f"[Schedule] Settings not found: {notification_settings_id}")
            return
        
        # is_active 확인 (비활성화 시 스킵)
        if not result.get("is_active"):
            print(f"[Schedule] Inactive - skip sending ({user_email})")
            return

        keywords = json.loads(result.get("keywords") or "[]")
        sources = json.loads(result.get("sources") or "[]")
        collect_count = result.get("collect_count") or 5
        language = result.get("language") or "ko"
        summary_length = result.get("summary_length") or "medium"
        
        # 논문 수집 (중복 발송 방지 필터링 포함)
        papers = NoticeService.collect_papers(keywords, sources, collect_count, user_email=user_email)
        
        if papers:
            # Discord에 발송
            from discord_module.notifications import DiscordNotificationService
            
            # 컬럼명 유연하게 처리
            webhook_url = result.get("discord_webhook_url") or result.get("webhook_url")
            raw_channel_id = result.get("discord_channel_id") or result.get("channel_id")

            # discord_channel_id가 JSON 배열 문자열일 수 있으므로 파싱
            channel_ids = []
            if raw_channel_id:
                try:
                    import json as _json
                    parsed = _json.loads(raw_channel_id)
                    if isinstance(parsed, list):
                        channel_ids = [str(c) for c in parsed if c]
                    else:
                        channel_ids = [str(parsed)]
                except (ValueError, TypeError):
                    channel_ids = [str(raw_channel_id)]

            if webhook_url:
                send_result = await DiscordNotificationService.send_papers(
                    webhook_url, papers, user_email=user_email
                )
            elif channel_ids:
                # 선택된 모든 채널에 발송 (마지막 채널 결과를 send_result로 사용)
                send_result = {"ok": False, "error": "발송 수단이 없음"}
                for cid in channel_ids:
                    send_result = await DiscordNotificationService.send_papers_to_channel(
                        cid, papers, user_email=user_email
                    )
            else:
                send_result = {"ok": False, "error": "발송 수단이 없음"}
            
            if send_result.get("ok"):
                status = "sent"
                # 발송 성공 시 기록
                NoticeService.record_sent_papers(user_email, papers)
            else:
                status = "failed"
                error_msg = send_result.get("error")
            
            NoticeService.record_alert(
                notification_settings_id, user_email, "scheduled",
                len(papers), status, error_msg
            )
            print(f"[Schedule] Send complete: {len(papers)} papers ({user_email})")
        else:
            NoticeService.record_alert(
                notification_settings_id, user_email, "scheduled",
                0, "sent", "해당하는 논문이 없습니다"
            )
            print(f"[Schedule] No papers collected ({user_email})")
    
    except Exception as e:
        print(f"[Schedule] Send failed: {e}")
        try:
            NoticeService.record_alert(
                notification_settings_id, user_email, "scheduled", 0,
                "failed", str(e)
            )
        except:
            pass

def get_cron_trigger(frequency: str):
    """
    주기에 따른 CronTrigger 반환
    모두 오후 2시(14:00)에 실행
    """
    if frequency == "daily":
        return CronTrigger(hour=14, minute=0)  # 매일 오후 2시
    elif frequency == "3days":
        # 3일마다 (처음 실행 후 3일 간격으로 설정)
        return CronTrigger(hour=14, minute=0)
    elif frequency == "weekly":
        return CronTrigger(hour=14, minute=0, day_of_week="0")  # 매주 월요일 오후 2시
    else:
        return CronTrigger(hour=14, minute=0)  # 기본값: 매일 오후 2시

def add_job(notification_settings_id: int, user_email: str, frequency: str):
    """
    스케줄 작업 추가
    """
    try:
        job_id = f"alert_{notification_settings_id}"
        
        # 기존 작업 제거
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # 새 작업 추가
        trigger = get_cron_trigger(frequency)
        scheduler.add_job(
            send_scheduled_alert,
            trigger,
            args=[notification_settings_id, user_email],
            id=job_id,
            replace_existing=True
        )
        return True
    except Exception as e:
        print(f"스케줄 추가 실패: {e}")
        return False

def remove_job(notification_settings_id: int):
    """
    스케줄 작업 제거
    """
    try:
        job_id = f"alert_{notification_settings_id}"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        return True
    except Exception as e:
        print(f"스케줄 제거 실패: {e}")
        return False

def start_scheduler():
    """
    스케줄러 시작
    """
    if not scheduler.running:
        scheduler.start()
        print("✅ 스케줄러 시작됨")

def stop_scheduler():
    """
    스케줄러 중지
    """
    if scheduler.running:
        scheduler.shutdown()
        print("⏹️ 스케줄러 중지됨")

def load_active_jobs():
    """
    활성 작업 로드 (시작 시)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT n.id, n.user_email, a.frequency
            FROM agent_configs a
            JOIN notification_settings n ON a.user_email = n.user_email
            WHERE a.is_active = 1
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        for notification_id, user_email, frequency in results:
            add_job(notification_id, user_email, frequency)
        
        print(f"✅ {len(results)}개 활성 작업 로드됨")
    except Exception as e:
        print(f"작업 로드 실패: {e}")
