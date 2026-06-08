from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import pymysql
import logging
import json
from .service import NoticeService
from auth import decode_jwt
from database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notice", tags=["notice"])

def get_email_from_token(authorization: Optional[str] = Header(None)) -> str:
    """Authorization 헤더에서 email 추출"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    token = authorization.split(" ", 1)[1]
    payload = decode_jwt(token)
    return payload["email"]

class NotificationSettingRequest(BaseModel):
    keywords: List[str]
    sources: List[str]
    language: str = "ko"
    summary_length: str = "medium"
    collect_count: int = 5
    frequency: str = "daily"

# Phase 3: 알림 설정 저장 + 즉시 1회 발송
@router.post("/settings")
async def save_notification_setting(
    request: NotificationSettingRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None)
):
    """
    Phase 3: 알림 설정 저장
    저장 성공 직후 즉시 논문 수집 + Discord 발송 (백그라운드 실행)
    """
    logger.info(f"🔵 [/api/notice/settings] 요청 수신")
    try:
        user_email = get_email_from_token(authorization)
        logger.info(f"✅ 사용자 이메일: {user_email}")
        
        # 설정 저장
        result = NoticeService.save_notification_setting(user_email, request.dict())
        logger.info(f"💾 설정 저장 결과: {result.get('ok')}")
        
        if not result.get("ok"):
            return result
        
        notification_id = result.get("notification_id")
        
        # 즉시 논문 수집 + 발송을 백그라운드 태스크로 등록
        if notification_id:
            background_tasks.add_task(
                run_immediate_collection,
                user_email=user_email,
                notification_id=notification_id,
                keywords=request.keywords,
                sources=request.sources,
                collect_count=request.collect_count,
                language=request.language,
                summary_length=request.summary_length
            )
        
        return {
            "ok": True,
            "message": "알림 설정이 저장되었습니다. 논문 수집 및 발송이 백그라운드에서 진행됩니다.",
            "agent_config_id": result.get("agent_config_id"),
            "notification_id": notification_id
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "설정 저장 실패"
        }

async def run_immediate_collection(user_email, notification_id, keywords, sources, collect_count, language, summary_length):
    """
    백그라운드에서 즉시 논문 수집 및 발송 실행
    """
    import asyncio
    try:
        logger.info(f"🚀 [Background] 즉시 수집 시작 ({user_email})")
        
        # 논문 수집 (중복 필터링 포함)
        # 시간 소요가 큰 동기 함수이므로 메인 이벤트 루프 블로킹 방지를 위해 스레드풀로 오프로드
        papers = await asyncio.to_thread(
            NoticeService.collect_papers,
            keywords, sources, collect_count, 
            user_email=user_email, 
            language=language, 
            summary_length=summary_length
        )
        logger.info(f"📚 수집된 논문 수: {len(papers)}개")
        
        send_status = "pending"
        send_error = None
        
        if papers:
            logger.info(f"🔍 Discord 채널 정보 조회 중... (notification_id: {notification_id})")
            # Discord 채널 정보 조회
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            # 호환성을 위해 모든 컬럼 조회
            cursor.execute("SELECT * FROM notification_settings WHERE id = %s", (notification_id,))
            channel_info = cursor.fetchone()
            conn.close()
            
            if channel_info:
                from discord_module.notifications import DiscordNotificationService
                
                # 컬럼명 유연하게 처리
                webhook_url = channel_info.get("discord_webhook_url") or channel_info.get("webhook_url")
                channel_id = channel_info.get("discord_channel_id") or channel_info.get("channel_id")
                
                if webhook_url:
                    send_result = await DiscordNotificationService.send_papers(
                        webhook_url, papers, user_email=user_email
                    )
                elif channel_id:
                    # discord_channel_id가 JSON 배열 문자열일 수 있으므로 파싱
                    channel_ids = []
                    try:
                        import json as _json
                        parsed = _json.loads(channel_id)
                        if isinstance(parsed, list):
                            channel_ids = [str(c) for c in parsed if c]
                        else:
                            channel_ids = [str(parsed)]
                    except (ValueError, TypeError):
                        channel_ids = [str(channel_id)]
                    
                    send_result = {"ok": False, "error": "발송 채널 없음"}
                    for cid in channel_ids:
                        send_result = await DiscordNotificationService.send_papers_to_channel(
                            cid, papers, user_email=user_email
                        )
                else:
                    send_result = {"ok": False, "error": "발송 수단(Webhook 또는 Channel ID)이 없습니다."}
                
                # 이메일 발송 추가
                email_connected = channel_info.get("email_connected")
                email_address = channel_info.get("email_address")
                if email_connected and email_address:
                    from email_module.service import send_papers_email
                    email_result = send_papers_email(email_address, papers, user_email=user_email)
                    if not send_result.get("ok") and email_result.get("ok"):
                        send_result = email_result # 이메일이라도 성공했으면 성공으로 간주
                
                if send_result.get("ok"):
                    send_status = "sent"
                    NoticeService.record_sent_papers(user_email, papers)
                else:
                    send_status = "failed"
                    send_error = send_result.get("error")
            else:
                send_error = "알림 설정(채널 정보)을 찾을 수 없습니다."
        else:
            send_status = "sent"
            send_error = "수집된 새로운 논문이 없습니다."
            
        # 발송 기록
        NoticeService.record_alert(
            notification_settings_id=notification_id,
            user_email=user_email,
            alert_type="immediate",
            papers_count=len(papers),
            status=send_status,
            error_message=send_error
        )
        logger.info(f"✅ [Background] 즉시 수집 완료 ({user_email})")
        
    except HTTPException:
        
        raise
        
    except Exception as e:
        logger.error(f"❌ [Background] 즉시 수집 오류: {e}")
        try:
            NoticeService.record_alert(
                notification_settings_id=notification_id,
                user_email=user_email,
                alert_type="immediate",
                status="failed",
                error_message=str(e)
            )
        except:
            pass

# Phase 3: 알림 설정 조회
@router.get("/settings")
def get_notification_setting(authorization: Optional[str] = Header(None)):
    """
    사용자의 알림 설정 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.get_notification_settings(user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "설정 조회 실패"
        }

# 즉시 수집 및 발송 실행
@router.post("/run-now")
async def run_now_with_current_settings(
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None)
):
    """
    현재 저장된 설정으로 즉시 논문 수집 및 발송 실행
    """
    try:
        user_email = get_email_from_token(authorization)
        
        # 저장된 설정 불러오기
        result = NoticeService.get_notification_settings(user_email)
        if not result.get("ok"):
            return result
        
        if not result.get("keywords") or not result.get("sources"):
            return {"ok": False, "message": "에이전트 설정(키워드, 소스)이 불완전합니다."}
            
        notification_id = None
        
        # DB에서 notification_settings id 가져오기 (get_notification_settings에는 알림 ID가 확실하게 없을 수도 있어서 직접 쿼리)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM notification_settings WHERE user_email=%s LIMIT 1", (user_email,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            notification_id = row[0]
            
        if not notification_id:
             return {"ok": False, "message": "알림 채널 설정이 존재하지 않습니다."}

        # 즉시 수집+발송 백그라운드 태스크 등록
        background_tasks.add_task(
            run_immediate_collection,
            user_email=user_email,
            notification_id=notification_id,
            keywords=result.get("keywords"),
            sources=result.get("sources"),
            collect_count=result.get("collect_count", 5),
            language=result.get("language", "ko"),
            summary_length=result.get("summary_length", "medium")
        )
        
        return {
            "ok": True,
            "message": "즉시 수집 및 발송 작업이 백그라운드에서 시작되었습니다."
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "실행 요청 실패"}


# 이메일 테스트 알림 전송
@router.post("/test/email")
async def test_email_notification(authorization: Optional[str] = Header(None)):
    """이메일로 테스트 알림 발송"""
    try:
        user_email = get_email_from_token(authorization)
        from email_module.service import send_test_notification
        result = send_test_notification(user_email)
        # 발송 기록
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM notification_settings WHERE user_email = %s LIMIT 1", (user_email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            NoticeService.record_alert(
                notification_settings_id=row[0],
                user_email=user_email,
                alert_type="test",
                papers_count=0,
                status="sent" if result.get("ok") else "failed",
                error_message=result.get("error") if not result.get("ok") else None
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "이메일 테스트 발송 실패"}

# Phase 3: 테스트 알림 전송
@router.post("/test/{channel}")
async def test_notification(
    channel: str,
    authorization: Optional[str] = Header(None)
):
    """
    Phase 3: 테스트 알림 전송 (Discord)
    """
    try:
        user_email = get_email_from_token(authorization)
        
        if channel != "discord":
            return {
                "ok": False,
                "message": "현재 Discord만 지원합니다"
            }
        
        # Discord 설정 확인
        conn = get_connection()
        
        # 먼저 regular cursor로 컬럼 확인
        regular_cursor = conn.cursor()
        regular_cursor.execute("SHOW COLUMNS FROM notification_settings")
        cols = {row[0] for row in regular_cursor.fetchall()}

        where_clause = "user_email = %s" if "user_email" in cols else "user_id = %s"
        fields = ["id"]
        if "discord_webhook_url" in cols:
            fields.append("discord_webhook_url")
        if "discord_channel_id" in cols:
            fields.append("discord_channel_id")
        elif "channel_id" in cols:
            fields.append("channel_id")

        # 이제 DictCursor로 데이터 조회
        dict_cursor = conn.cursor(pymysql.cursors.DictCursor)
        dict_cursor.execute(
            f"SELECT {', '.join(fields)} FROM notification_settings WHERE {where_clause} ORDER BY id DESC LIMIT 1",
            (user_email,)
        )
        result = dict_cursor.fetchone()
        conn.close()
        
        if not result:
            return {
                "ok": False,
                "message": "Discord 연동이 필요합니다"
            }

        notification_id = result.get("id")
        webhook_url = result.get("discord_webhook_url")
        raw_channel_id = result.get("discord_channel_id") or result.get("channel_id")

        # discord_channel_id가 JSON 배열 문자열일 수 있으므로 파싱
        channel_ids = []
        if raw_channel_id:
            try:
                parsed = json.loads(raw_channel_id)
                if isinstance(parsed, list):
                    channel_ids = [str(c) for c in parsed if c]
                else:
                    channel_ids = [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                channel_ids = [str(raw_channel_id)]

        # 테스트 메시지 발송
        from discord_module.notifications import DiscordNotificationService
        if webhook_url:
            send_result = await DiscordNotificationService.send_test_message(webhook_url)
        elif channel_ids:
            # 선택된 채널 모두에 테스트 전송 (첫 번째 채널만 결과 반환)
            send_result = None
            for cid in channel_ids:
                send_result = await DiscordNotificationService.send_test_message_to_channel(cid)
        else:
            return {
                "ok": False,
                "message": "채널을 먼저 선택해주세요"
            }

        
        # 발송 기록 저장
        NoticeService.record_alert(
            notification_settings_id=notification_id,
            user_email=user_email,
            alert_type="test",
            papers_count=0,
            status="sent" if send_result.get("ok") else "failed",
            error_message=send_result.get("error") if not send_result.get("ok") else None
        )
        
        return send_result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "테스트 발송 실패"
        }

# Phase 4-5: 알림 일시정지
@router.patch("/pause")
def pause_notification(authorization: Optional[str] = Header(None)):
    """
    Phase 4-5: 알림 일시정지
    """
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.pause_notification(user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "일시정지 실패"
        }

# Phase 4-5: 알림 재개
@router.patch("/resume")
def resume_notification(authorization: Optional[str] = Header(None)):
    """
    Phase 4-5: 알림 재개
    """
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.resume_notification(user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "재개 실패"
        }

# Phase 4-5: 에이전트 상태 조회
@router.get("/status")
def get_agent_status(authorization: Optional[str] = Header(None)):
    """
    Phase 4-5: 에이전트 상태 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.get_agent_status(user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "상태 조회 실패"
        }

# Phase 5: 알림 설정 삭제
@router.delete("/settings/{user_email}")
def delete_notification_setting(
    user_email: str,
    authorization: Optional[str] = Header(None)
):
    """
    Phase 5: 알림 설정 삭제
    설정+토큰+스케줄 기록만 삭제, 보관함은 유지
    """
    try:
        current_email = get_email_from_token(authorization)
        
        # 자신의 데이터만 삭제 가능
        if current_email != user_email:
            raise HTTPException(status_code=403, detail="권한 없음")
        
        result = NoticeService.delete_notification_setting(user_email)
        return result
    except HTTPException:
        raise
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "삭제 실패"
        }

# 이메일 채널 연결 저장
@router.patch("/email/connect")
def connect_email_channel(authorization: Optional[str] = Header(None)):
    """현재 로그인 이메일로 이메일 알림 채널 연결"""
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.connect_email_channel(user_email, user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "이메일 연결 실패"}

# 이메일 채널 연결 해제
@router.patch("/email/disconnect")
def disconnect_email_channel(authorization: Optional[str] = Header(None)):
    """이메일 알림 채널 연결 해제"""
    try:
        user_email = get_email_from_token(authorization)
        result = NoticeService.disconnect_email_channel(user_email)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e), "message": "이메일 해제 실패"}

# Phase 6: 대시보드 KPI 통계 조회
@router.get("/stats")
def get_dashboard_stats(authorization: Optional[str] = Header(None)):
    """
    대시보드 KPI 통계 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        return NoticeService.get_dashboard_stats(user_email)
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}

# Phase 6: 수집 트렌드 조회
@router.get("/stats/trend")
def get_trend_data(
    period: str = "weekly",
    authorization: Optional[str] = Header(None)
):
    """
    수집 트렌드 차트 데이터 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        return NoticeService.get_trend_data(user_email, period)
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}
