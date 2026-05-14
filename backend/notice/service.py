# Notice Service - 알림 설정/저장/테스트 비즈니스 로직
import pymysql
import json
import sys
import os
from datetime import datetime
from database import get_connection
from pathlib import Path

# api_get 모듈 임포트
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from api_get import (
        arxiv_search, crossref_search, semantic_search, core_search,
        remove_duplicates, sort_papers_by_recency, normalize_title
    )
    from config import settings
    print("[notice/service.py] api_get & config import success")
except ImportError as e:
    print(f"[notice/service.py] api_get import failed: {e}")
    arxiv_search = crossref_search = semantic_search = core_search = None
    remove_duplicates = sort_papers_by_recency = normalize_title = None
    settings = None

# agent.py의 요약 함수들 임포트
try:
    from agent import translate_abstract, summarize_body, read_paper_pdf, is_relevant
    print("[notice/service.py] agent import success")
except ImportError as e:
    print(f"[notice/service.py] agent import failed: {e}")
    translate_abstract = summarize_body = read_paper_pdf = is_relevant = None

class NoticeService:
    def __init__(self):
        pass
    
    @staticmethod
    def save_notification_setting(user_email: str, config: dict) -> dict:
        """
        Phase 3: 알림 설정 저장
        agent_configs + notification_settings를 함께 저장
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # agent_configs 저장
            keywords = json.dumps(config.get("keywords", []))
            sources = json.dumps(config.get("sources", []))
            
            cursor.execute("""
                INSERT INTO agent_configs 
                (user_email, keywords, sources, language, summary_length, 
                 collect_count, frequency, is_active, is_configured)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE)
                ON DUPLICATE KEY UPDATE
                keywords=%s,
                sources=%s,
                language=%s,
                summary_length=%s,
                collect_count=%s,
                frequency=%s,
                is_active=TRUE,
                is_configured=TRUE,
                updated_at=CURRENT_TIMESTAMP
            """, (
                user_email,
                keywords,
                sources,
                config.get("language", "ko"),
                config.get("summary_length", "medium"),
                config.get("collect_count", 5),
                config.get("frequency", "daily"),
                keywords,
                sources,
                config.get("language", "ko"),
                config.get("summary_length", "medium"),
                config.get("collect_count", 5),
                config.get("frequency", "daily")
            ))
            
            agent_config_id = cursor.lastrowid
            conn.commit()
            
            # notification_settings 조회 (이미 있는 경우)
            cursor.execute("""
                SELECT id FROM notification_settings WHERE user_email=%s
            """, (user_email,))
            notification_record = cursor.fetchone()
            notification_id = notification_record[0] if notification_record else None
            
            conn.close()
            
            # 스케줄러에 작업 추가/업데이트
            if notification_id:
                from .scheduler import add_job
                add_job(notification_id, user_email, config.get("frequency", "daily"))
            
            return {
                "ok": True,
                "agent_config_id": agent_config_id,
                "notification_id": notification_id,
                "message": "알림 설정 저장 및 스케줄 등록 완료"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "알림 설정 저장 실패"
            }
    
    @staticmethod
    def get_sent_papers(user_email: str) -> set:
        """
        사용자에게 이미 발송된 논문 ID 및 제목 목록 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT paper_id, title FROM sent_papers WHERE user_email = %s", (user_email,))
            rows = cursor.fetchall()
            conn.close()
            
            sent_keys = set()
            for pid, title in rows:
                if pid: sent_keys.add(f"id:{pid}")
                if title: sent_keys.add(f"title:{normalize_title(title)}")
            return sent_keys
        except Exception as e:
            print(f"발송 기록 조회 실패: {e}")
            return set()

    @staticmethod
    def record_sent_papers(user_email: str, papers: list):
        """
        발송된 논문들을 기록하여 중복 방지
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            for paper in papers:
                pid = paper.get("id") or paper.get("paperId") or ""
                title = paper.get("title", "")
                cursor.execute("""
                    INSERT IGNORE INTO sent_papers (user_email, paper_id, title)
                    VALUES (%s, %s, %s)
                """, (user_email, pid, title))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"발송 기록 저장 실패: {e}")

    @staticmethod
    def collect_papers(keywords_list: list, sources: list, collect_count: int, user_email: str = None) -> list:
        """
        설정에 맞게 논문 수집 + 초록 번역 + 본문 요약
        user_email이 있으면 중복 발송 방지 필터링 적용
        """
        if not arxiv_search or not settings:
            return []
        
        # 이미 보낸 논문 가져오기
        sent_history = set()
        if user_email:
            sent_history = NoticeService.get_sent_papers(user_email)
        
        try:
            papers = []
            
            # 각 키워드별로 논문 수집
            for keyword in keywords_list[:3]:  # 최대 3개 키워드
                keyword = keyword.strip()
                if not keyword:
                    continue
                
                # 중복 방지 필터링을 고려하여 평소보다 3배 더 많이 수집 시도
                limit_per_source = max(15, (collect_count * 3))
                
                for source in sources:
                    try:
                        # 소스명 정규화 (대소문자 무시)
                        source_lower = source.lower()
                        
                        source_results = []
                        if source_lower == "arxiv":
                            source_results = arxiv_search(keyword, limit_per_source)
                        elif source_lower == "crossref":
                            source_results = crossref_search(keyword, limit_per_source)
                        elif source_lower in ["semantic", "semantic scholar"]:
                            source_results = semantic_search(keyword, settings.semantic_scholar_api_key, limit_per_source)
                        elif source_lower == "core":
                            source_results = core_search(keyword, settings.core_api_key, limit_per_source)
                        
                        # 중복 방지 필터링 (이미 발송된 논문 제외)
                        for p in source_results:
                            pid = p.get("id") or p.get("paperId") or ""
                            title = normalize_title(p.get("title", ""))
                            # ID 또는 제목으로 중복 체크
                            if f"id:{pid}" in sent_history or f"title:{title}" in sent_history:
                                continue
                            
                            # 현재 수집된 목록 내 중복 체크
                            if any((p.get("id") or p.get("paperId")) == (x.get("id") or x.get("paperId")) for x in papers):
                                continue
                            if any(normalize_title(p.get("title", "")) == normalize_title(x.get("title", "")) for x in papers):
                                continue
                                
                            papers.append(p)
                            
                            # 필요한 개수를 다 채웠으면 해당 키워드 중단
                            if len(papers) >= collect_count * 2: # 여유있게 수집 후 나중에 자름
                                break
                                
                    except Exception as e:
                        print(f"({source}) {keyword} 수집 중 오류: {e}")
                        continue
            
            # 중복 제거 및 정렬
            if papers and remove_duplicates and sort_papers_by_recency:
                papers = remove_duplicates(papers)
                papers = sort_papers_by_recency(papers)
            
            # 사용자가 요청한 개수만큼 딱 맞춰서 반환 (중복 제외 후에도 개수 유지)
            papers = papers[:collect_count]
            
            # 각 논문의 초록 번역 및 본문 요약 추가
            if translate_abstract:
                for paper in papers:
                    try:
                        # 초록 번역
                        if paper.get("abstract") and not paper.get("abstract_ko"):
                            paper["abstract_ko"] = translate_abstract(paper.get("abstract", ""))
                        
                        # 본문 요약 (시간 소요 - 선택적)
                        pdf_url = paper.get("pdf_url") or paper.get("url")
                        if pdf_url and summarize_body and read_paper_pdf:
                            try:
                                body_text = read_paper_pdf(pdf_url, max_pages=3)  # 처음 3페이지만 (속도 위해 축소)
                                if body_text:
                                    paper["body_summary"] = summarize_body(
                                        paper.get("abstract", ""),
                                        body_text
                                    )
                            except Exception as e:
                                print(f"본문 요약 실패: {e}")
                                paper["body_summary"] = None
                    except Exception as e:
                        print(f"논문 처리 중 오류: {e}")
                        continue
            
            return papers
        except Exception as e:
            print(f"논문 수집 중 오류: {e}")
            return []
    
    @staticmethod
    def format_paper_message(paper: dict, language: str = "ko") -> str:
        """
        논문 정보를 메시지 형식으로 포맷
        형식: 제목\n\n저자 · 발행일 · 카테고리 · NEW\n\n요약\n\n인용 수 · 수집 일자 · 출처 ↗
        """
        title = paper.get("title", "제목 없음")
        authors = paper.get("authors", [])
        published = paper.get("published") or paper.get("year") or paper.get("publishedDate") or "미상"
        abstract = paper.get("abstract") or paper.get("summary", "요약 없음")
        categories = paper.get("categories") or paper.get("fieldsOfStudy") or []
        link = paper.get("link") or paper.get("url") or ""
        source = paper.get("source", "Unknown")
        citation_count = paper.get("citationCount") or 0
        
        # 저자 문자열
        authors_str = ", ".join(authors[:3]) if isinstance(authors, list) else str(authors)
        
        # 카테고리 문자열 (최대 3개)
        categories_str = ""
        if categories:
            if isinstance(categories, list):
                cat_list = categories[:3]
            else:
                cat_list = str(categories).split(",")[:3]
            categories_str = " · ".join([str(c).strip() for c in cat_list])
        
        # 발행일 포맷팅
        date_str = str(published)[:10] if published else "미상"
        
        # 메시지 구성
        message = f"**{title}**\n\n"
        if authors_str:
            message += f"{authors_str} · "
        message += f"{date_str}"
        if categories_str:
            message += f" · {categories_str}"
        message += " · NEW\n\n"
        message += f"{abstract[:300]}...\n\n" if len(abstract) > 300 else f"{abstract}\n\n"
        message += f"인용 {citation_count} · 수집 {datetime.now().strftime('%Y.%m.%d')} · {source}"
        if link:
            message += f" [↗]({link})"
        
        return message
    
    @staticmethod
    def build_papers_embed_list(papers: list, language: str = "ko", summary_length: str = "medium") -> list:
        """
        논문 리스트를 Discord Embed 형식으로 변환
        (번역된 초록 + 본문 요약 포함)
        """
        embeds = []
        
        for i, paper in enumerate(papers[:10], 1):
            title = paper.get("title", "제목 없음")[:256]
            authors = paper.get("authors", [])
            published = paper.get("published") or paper.get("year") or paper.get("publishedDate") or "미상"
            abstract = paper.get("abstract") or paper.get("summary", "요약 없음")
            abstract_ko = paper.get("abstract_ko", "")  # 번역된 초록
            body_summary = paper.get("body_summary", "")  # 본문 요약
            categories = paper.get("categories") or paper.get("fieldsOfStudy") or []
            link = paper.get("link") or paper.get("url") or ""
            source = paper.get("source", "Unknown")
            citation_count = paper.get("citationCount") or 0
            
            # 요약 길이 조정 (한국어 초록 우선, 없으면 영문 abstract)
            summary_to_use = abstract_ko if abstract_ko else abstract
            
            if summary_length == "short":
                summary_text = summary_to_use[:100]
            elif summary_length == "medium":
                summary_text = summary_to_use[:200]
            else:  # long
                summary_text = summary_to_use[:400]
            
            # 저자 문자열
            authors_str = ", ".join(authors[:2]) if isinstance(authors, list) else str(authors)
            
            # 카테고리 문자열
            categories_str = ""
            if categories:
                if isinstance(categories, list):
                    cat_list = categories[:2]
                else:
                    cat_list = str(categories).split(",")[:2]
                categories_str = " · ".join([str(c).strip() for c in cat_list])
            
            # Embed 필드 구성
            fields = [
                {
                    "name": "저자",
                    "value": authors_str if authors_str else "저자 정보 없음",
                    "inline": False
                },
                {
                    "name": "발행",
                    "value": str(published),
                    "inline": True
                },
                {
                    "name": "인용",
                    "value": str(citation_count),
                    "inline": True
                },
                {
                    "name": "카테고리",
                    "value": categories_str if categories_str else "미분류",
                    "inline": False
                }
            ]
            
            # 번역된 초록 추가
            if abstract_ko:
                fields.append({
                    "name": "초록 (한국어)",
                    "value": abstract_ko[:1024] if len(abstract_ko) > 1024 else abstract_ko,
                    "inline": False
                })
            
            # 본문 요약 추가
            if body_summary:
                fields.append({
                    "name": "본문 요약",
                    "value": body_summary[:1024] if len(body_summary) > 1024 else body_summary,
                    "inline": False
                })
            
            # 출처 필드
            fields.append({
                "name": "출처",
                "value": f"[{source}]({link})" if link else source,
                "inline": False
            })
            
            # Embed 구성
            embed = {
                "title": f"{i}. {title}",
                "description": summary_text + ("..." if len(summary_to_use) > len(summary_text) else ""),
                "url": link if link else None,
                "color": 0x5865F2,  # Discord 색상
                "fields": fields
            }
            
            embeds.append(embed)
        
        # 요약 embed 추가 (맨 앞)
        summary_embed = {
            "title": f"📰 수집 결과 ({len(papers)}개)",
            "description": f"{len(papers)}개의 새로운 논문을 수집했습니다!",
            "color": 0x57F287,
            "footer": {
                "text": "Paper Agent 자동 수집"
            }
        }
        
        return [summary_embed] + embeds
    
    @staticmethod
    def get_notification_settings(user_email: str) -> dict:
        """
        사용자의 알림 설정 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("""
                SELECT 
                    a.id,
                    a.keywords,
                    a.sources,
                    a.language,
                    a.summary_length,
                    a.collect_count,
                    a.frequency,
                    a.is_active,
                    a.is_configured,
                    n.id as notification_id,
                    n.discord_username,
                    n.discord_channel_id,
                    n.last_discord_test_status,
                    n.last_discord_test_at
                FROM agent_configs a
                LEFT JOIN notification_settings n ON a.user_email = n.user_email
                WHERE a.user_email = %s
            """, (user_email,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "ok": True,
                    "agent_config_id": result.get("id"),
                    "keywords": json.loads(result.get("keywords", "[]")),
                    "sources": json.loads(result.get("sources", "[]")),
                    "language": result.get("language"),
                    "summary_length": result.get("summary_length"),
                    "collect_count": result.get("collect_count"),
                    "frequency": result.get("frequency"),
                    "is_active": bool(result.get("is_active")),
                    "is_configured": bool(result.get("is_configured")),
                    "notifications": {
                        "discord": {
                            "connected": bool(result.get("discord_username")),
                            "username": result.get("discord_username"),
                            "channel_id": result.get("discord_channel_id"),
                            "lastTestStatus": result.get("last_discord_test_status"),
                            "lastTestAt": int(result.get("last_discord_test_at").timestamp()) if result.get("last_discord_test_at") else None
                        }
                    }
                }
            else:
                return {
                    "ok": True,
                    "message": "저장된 설정 없음"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "설정 조회 실패"
            }
    
    @staticmethod
    def record_alert(notification_settings_id: int, user_email: str, 
                     alert_type: str = "scheduled", papers_count: int = 0, 
                     status: str = "success", error_message: str = None) -> dict:
        """
        Phase 3: 발송 기록 저장
        즉시 발송/정시 발송/테스트 모두 기록
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO scheduled_alerts 
                (notification_settings_id, user_email, alert_type, papers_count, status, error_message)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                notification_settings_id,
                user_email,
                alert_type,
                papers_count,
                status,
                error_message
            ))
            
            alert_id = cursor.lastrowid
            
            # last_discord_test_status 업데이트
            if alert_type == "test":
                cursor.execute("""
                    UPDATE notification_settings
                    SET last_discord_test_status=%s, last_discord_test_at=CURRENT_TIMESTAMP
                    WHERE id=%s
                """, (status, notification_settings_id))
            
            # last_sent_at 업데이트
            if alert_type in ["scheduled", "immediate", "resume"]:
                cursor.execute("""
                    UPDATE agent_configs
                    SET updated_at=CURRENT_TIMESTAMP
                    WHERE user_email=%s
                """, (user_email,))
            
            conn.commit()
            conn.close()
            
            return {
                "ok": True,
                "alert_id": alert_id,
                "message": f"{alert_type} 발송 기록 저장"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "발송 기록 저장 실패"
            }
    
    @staticmethod
    def delete_notification_setting(user_email: str) -> dict:
        """
        Phase 5: 알림 설정 삭제
        설정+토큰+스케줄 기록만 삭제, 보관함은 유지
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # notification_settings에서 id 조회
            cursor.execute("""
                SELECT id FROM notification_settings WHERE user_email=%s
            """, (user_email,))
            notification_record = cursor.fetchone()
            
            if notification_record:
                notification_id = notification_record[0]
                # scheduled_alerts 삭제
                cursor.execute("""
                    DELETE FROM scheduled_alerts WHERE notification_settings_id=%s
                """, (notification_id,))
                # notification_settings 삭제
                cursor.execute("""
                    DELETE FROM notification_settings WHERE id=%s
                """, (notification_id,))
            
            # agent_configs 삭제
            cursor.execute("""
                DELETE FROM agent_configs WHERE user_email=%s
            """, (user_email,))
            
            conn.commit()
            conn.close()
            
            return {
                "ok": True,
                "message": "알림 설정 삭제 완료 (보관함 유지됨)"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "삭제 실패"
            }
    
    @staticmethod
    def pause_notification(user_email: str) -> dict:
        """
        Phase 4-5: 알림 일시정지
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE agent_configs
                SET is_active=0, updated_at=CURRENT_TIMESTAMP
                WHERE user_email=%s
            """, (user_email,))
            
            conn.commit()
            conn.close()
            
            return {
                "ok": True,
                "message": "알림 일시정지됨"
            }
        except Exception as e:
            print(f"[NoticeService] pause_notification error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "message": "일시정지 실패"
            }
    
    @staticmethod
    def resume_notification(user_email: str) -> dict:
        """
        Phase 4-5: 알림 재개
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # 1. 에이전트 활성화 상태 변경
            cursor.execute("""
                UPDATE agent_configs
                SET is_active=1, updated_at=CURRENT_TIMESTAMP
                WHERE user_email=%s
            """, (user_email,))
            
            # 2. 관련 알림 설정 ID 조회
            cursor.execute("SELECT id FROM notification_settings WHERE user_email=%s LIMIT 1", (user_email,))
            row = cursor.fetchone()
            
            if row:
                notification_id = row[0]
                # 3. 발송 기록 추가 (옵션)
                try:
                    cursor.execute("""
                        INSERT INTO scheduled_alerts (notification_settings_id, user_email, alert_type, status)
                        VALUES (%s, %s, 'resume', 'success')
                    """, (notification_id, user_email))
                except:
                    pass
            
            conn.commit()
            conn.close()
            return {"ok": True, "message": "알림 재개됨"}
        except Exception as e:
            print(f"[NoticeService] resume_notification error: {e}")
            return {"ok": False, "error": str(e), "message": "재개 실패"}
    
    @staticmethod
    def get_agent_status(user_email: str) -> dict:
        """
        Phase 4-5: 에이전트 상태 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("""
                SELECT 
                    a.is_active,
                    a.is_configured,
                    a.frequency,
                    a.collect_count,
                    a.language,
                    a.summary_length,
                    a.keywords,
                    a.sources,
                    a.updated_at,
                    a.created_at,
                    n.discord_username,
                    n.discord_channel_id,
                    n.last_discord_test_status,
                    n.last_discord_test_at
                FROM agent_configs a
                LEFT JOIN notification_settings n ON a.user_email = n.user_email
                WHERE a.user_email=%s
            """, (user_email,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "ok": True,
                    "is_active": bool(result.get("is_active")),
                    "is_configured": bool(result.get("is_configured")),
                    "frequency": result.get("frequency"),
                    "collect_count": result.get("collect_count"),
                    "language": result.get("language"),
                    "summary_length": result.get("summary_length"),
                    "keywords": json.loads(result.get("keywords", "[]")),
                    "sources": json.loads(result.get("sources", "[]")),
                    "notifications": {
                        "discord": {
                            "connected": bool(result.get("discord_username")),
                            "username": result.get("discord_username"),
                            "channel_id": result.get("discord_channel_id"),
                            "lastTestStatus": result.get("last_discord_test_status"),
                            "lastTestAt": int(result.get("last_discord_test_at").timestamp()) if result.get("last_discord_test_at") else None,
                        }
                    },
                    "updated_at": int(result.get("updated_at").timestamp()) if result.get("updated_at") else None,
                    "created_at": int(result.get("created_at").timestamp()) if result.get("created_at") else None
                }
            else:
                return {
                    "ok": True,
                    "is_active": False,
                    "is_configured": False,
                    "frequency": None,
                    "collect_count": None,
                    "language": None,
                    "summary_length": None,
                    "notifications": {
                        "discord": {
                            "connected": False,
                            "username": None,
                            "channel_id": None,
                            "lastTestStatus": None,
                            "lastTestAt": None,
                        }
                    },
                    "message": "에이전트 설정 없음"
                }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "상태 조회 실패"
            }
    def get_dashboard_stats(user_email: str) -> dict:
        """
        대시보드 KPI 통계 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            # 1. 총 수집 수
            cursor.execute("SELECT COUNT(*) as total FROM papers WHERE user_email = %s", (user_email,))
            total = cursor.fetchone()["total"]
            
            # 2. 이번 주 신규 (최근 7일)
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM papers 
                WHERE user_email = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (user_email,))
            weekly = cursor.fetchone()["count"]
            
            # 3. 지난 주 수집량 (증가율 계산용)
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM papers 
                WHERE user_email = %s 
                AND created_at >= DATE_SUB(NOW(), INTERVAL 14 DAY)
                AND created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)
            """, (user_email,))
            last_weekly = cursor.fetchone()["count"]
            
            growth = "0%"
            if last_weekly > 0:
                rate = ((weekly - last_weekly) / last_weekly) * 100
                growth = f"{rate:+.1f}%"
            elif weekly > 0:
                growth = "+100%"

            # 4. 인기 카테고리 TOP 3 (키워드 대신 카테고리 활용)
            cursor.execute("""
                SELECT category as label, COUNT(*) as count
                FROM papers
                WHERE user_email = %s AND category IS NOT NULL AND category != ''
                GROUP BY category
                ORDER BY count DESC
                LIMIT 3
            """, (user_email,))
            top_keywords = cursor.fetchall()

            conn.close()
            
            return {
                "ok": True,
                "stats": {
                    "totalPapers": total,
                    "weeklyAdded": weekly,
                    "weeklyGrowth": growth,
                    "topKeywords": top_keywords,
                    "updatedAt": datetime.now().strftime("%Y.%m.%d %H:%M")
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def get_trend_data(user_email: str, period: str = "weekly") -> dict:
        """
        수집 트렌드 차트 데이터 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            if period == "monthly":
                # 최근 12개월
                cursor.execute("""
                    SELECT DATE_FORMAT(created_at, '%Y-%m') as label, COUNT(*) as count
                    FROM papers
                    WHERE user_email = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
                    GROUP BY label
                    ORDER BY label ASC
                """, (user_email,))
            elif period == "yearly":
                # 연도별
                cursor.execute("""
                    SELECT DATE_FORMAT(created_at, '%Y') as label, COUNT(*) as count
                    FROM papers
                    WHERE user_email = %s
                    GROUP BY label
                    ORDER BY label ASC
                """, (user_email,))
            else:
                # 주별 (최근 12주)
                cursor.execute("""
                    SELECT DATE_FORMAT(created_at, '%x-%v') as label, COUNT(*) as count
                    FROM papers
                    WHERE user_email = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 12 WEEK)
                    GROUP BY label
                    ORDER BY label ASC
                """, (user_email,))
            
            rows = cursor.fetchall()
            conn.close()
            
            return {
                "ok": True,
                "trend": {
                    "labels": [row["label"] for row in rows],
                    "data": [row["count"] for row in rows]
                }
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
