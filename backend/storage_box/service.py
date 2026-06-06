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
        bookmarks 테이블 컬럼: id, user_email, paper_id, title, summary, link, source, created_at
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # paper_id 정규화: URL 형태면 arxiv ID만 추출
            raw_id = str(paper.get("id") or paper.get("arxiv_id") or paper.get("paper_id") or "")
            link = paper.get("link") or ""
            
            # arxiv URL에서 ID 추출 (http://arxiv.org/abs/2606.03969v1 → 2606.03969v1)
            def extract_arxiv_id(s: str) -> str:
                if not s:
                    return s
                if "arxiv.org/abs/" in s:
                    return s.split("arxiv.org/abs/")[-1].strip("/")
                return s
            
            paper_id = extract_arxiv_id(raw_id) or extract_arxiv_id(link) or raw_id or link
            
            title = paper.get("title") or "제목 없음"
            summary = paper.get("summary") or ""
            source = paper.get("source") or "unknown"
            
            # link가 없으면 arxiv_id로 구성
            if not link and paper_id:
                if paper_id.startswith("http"):
                    link = paper_id
                else:
                    link = f"https://arxiv.org/abs/{paper_id}"
            
            # 정보 부족 시 papers 테이블에서 보완
            if not summary:
                try:
                    clean_id = paper_id.split("/")[-1] if "/" in paper_id else paper_id
                    cursor.execute("""
                        SELECT title, summary, abstract FROM papers 
                        WHERE arxiv_id LIKE %s OR id = %s
                        LIMIT 1
                    """, (f"%{clean_id}%", clean_id))
                    info = cursor.fetchone()
                    if info:
                        if not title or title == "제목 없음": title = info[0] or title
                        if not summary: summary = info[1] or info[2] or ""
                except:
                    pass

            # 중복 체크 (paper_id 또는 link 기준 — 양쪽 모두 확인)
            cursor.execute("""
                SELECT id FROM bookmarks 
                WHERE user_email = %s AND (paper_id = %s OR paper_id = %s)
            """, (user_email, paper_id, link))
            if cursor.fetchone():
                conn.close()
                return {
                    "ok": True,
                    "message": "이미 보관함에 있는 논문입니다.",
                    "already_exists": True
                }

            # 저장 — INSERT IGNORE로 unique 충돌 시 조용히 처리
            paper_data = json.dumps(paper, ensure_ascii=False)
            cursor.execute("""
                INSERT IGNORE INTO bookmarks 
                (user_id, user_email, paper_id, paper_data, title, summary, link, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_email, user_email, paper_id, paper_data, title, summary, link, source))
            
            bookmark_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # INSERT IGNORE가 충돌로 실제 삽입 안 된 경우
            if bookmark_id == 0:
                return {
                    "ok": True,
                    "message": "이미 보관함에 있는 논문입니다.",
                    "already_exists": True
                }
            
            return {
                "ok": True,
                "bookmark_id": bookmark_id,
                "message": "논문 저장 완료"
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "ok": False,
                "error": str(e),
                "message": "저장 실패"
            }

    
    @staticmethod
    def get_bookmarks(user_email: str) -> dict:
        """
        저장한 논문 목록 조회 (본인 이메일 기준만)
        """
        try:
            conn = get_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            cursor.execute("""
                SELECT 
                    id, paper_id, title, summary, link, source, paper_data, bookmarked_at AS created_at
                FROM bookmarks
                WHERE user_email = %s
                ORDER BY bookmarked_at DESC
            """, (user_email,))
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for row in rows:
                data_dict = {}
                try:
                    if row.get("paper_data"):
                        data_dict = json.loads(row["paper_data"])
                except:
                    pass
                
                authors = data_dict.get("authors", "")
                citations = data_dict.get("citations", 0) or data_dict.get("citationCount", 0)
                
                results.append({
                    "id": row["id"],
                    "paper_id": row.get("paper_id", ""),
                    "title": row.get("title") or "제목 없음",
                    "summary": row.get("summary") or "",
                    "link": row.get("link") or "",
                    "source": row.get("source") or "unknown",
                    "authors": authors,
                    "citations": citations,
                    "bookmarked_at": str(row.get("created_at", "")),
                })
            
            return {
                "ok": True,
                "bookmarks": results,
                "count": len(results)
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
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
                WHERE id = %s AND user_email = %s
            """, (bookmark_id, user_email))
            
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

