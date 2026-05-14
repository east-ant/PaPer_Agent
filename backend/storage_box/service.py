# Storage Box Service - 보관함 CRUD
import pymysql
import json
from database import get_connection

class StorageBoxService:
    def __init__(self):
        pass
    
    @staticmethod
    def save_bookmark(user_email: str, paper: dict) -> dict:
        """
        논문 저장 (보관함)
        실제 DB 컬럼: user_id, paper_id, paper_data(JSON), user_email, bookmarked_at
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            paper_id = paper.get("id") or paper.get("arxiv_id") or paper.get("paper_id") or ""
            title = paper.get("title")
            summary = paper.get("summary")
            link = paper.get("link")
            
            # 정보가 부족하면 papers 테이블에서 조회
            if not title or not summary:
                try:
                    cursor.execute("""
                        SELECT title, summary, abstract FROM papers 
                        WHERE arxiv_id = %s OR id = %s
                        LIMIT 1
                    """, (paper_id, paper_id))
                    info = cursor.fetchone()
                    if info:
                        if not title: title = info[0]
                        if not summary: summary = info[1] or info[2]
                except:
                    pass

            # title, summary, link, source 등을 paper_data JSON에 저장
            paper_data = {
                "title": title or "제목 없음",
                "summary": summary or "",
                "link": link or "",
                "source": paper.get("source", "unknown"),
            }
            
            # 중복 체크
            cursor.execute("""
                SELECT id FROM bookmarks 
                WHERE user_email = %s AND paper_id = %s
            """, (user_email, paper_id))
            if cursor.fetchone():
                conn.close()
                return {
                    "ok": True,
                    "message": "이미 보관함에 있는 논문입니다.",
                    "already_exists": True
                }

            cursor.execute("""
                INSERT INTO bookmarks 
                (user_id, paper_id, paper_data, user_email)
                VALUES (%s, %s, %s, %s)
            """, (
                user_email,       # user_id = user_email
                paper_id,
                json.dumps(paper_data, ensure_ascii=False),
                user_email,
            ))
            
            bookmark_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {
                "ok": True,
                "bookmark_id": bookmark_id,
                "message": "논문 저장 완료"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "저장 실패"
            }
    
    @staticmethod
    def get_bookmarks(user_email: str) -> dict:
        """
        저장한 논문 목록 조회
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("""
                SELECT 
                    id, paper_id, paper_data, bookmarked_at
                FROM bookmarks
                WHERE user_email = %s OR user_id = %s
                ORDER BY bookmarked_at DESC
            """, (user_email, user_email))
            
            rows = cursor.fetchall()
            conn.close()
            
            # paper_data JSON을 파싱하여 플랫 구조로 반환
            results = []
            for row in rows:
                data = row.get("paper_data") or {}
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except:
                        data = {}
                results.append({
                    "id": row["id"],
                    "paper_id": row["paper_id"],
                    "title": data.get("title", "제목 없음"),
                    "summary": data.get("summary", ""),
                    "link": data.get("link", ""),
                    "source": data.get("source", "unknown"),
                    "bookmarked_at": str(row.get("bookmarked_at", "")),
                })
            
            return {
                "ok": True,
                "bookmarks": results,
                "count": len(results)
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "조회 실패"
            }
    
    @staticmethod
    def delete_bookmark(bookmark_id: int, user_email: str) -> dict:
        """
        저장한 논문 제거
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # 자신의 북마크만 삭제 가능
            cursor.execute("""
                DELETE FROM bookmarks
                WHERE id = %s AND (user_email = %s OR user_id = %s)
            """, (bookmark_id, user_email, user_email))
            
            if cursor.rowcount == 0:
                conn.close()
                return {
                    "ok": False,
                    "message": "해당 북마크를 찾을 수 없거나 권한이 없습니다"
                }
            
            conn.commit()
            conn.close()
            
            return {
                "ok": True,
                "message": "북마크 삭제 완료"
            }
        except Exception as e:
            return {
                "ok": False,
                "error": str(e),
                "message": "삭제 실패"
            }
