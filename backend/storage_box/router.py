from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from .service import StorageBoxService
from auth import decode_jwt

router = APIRouter(prefix="/api/storage_box", tags=["storage_box"])

def get_email_from_token(authorization: Optional[str] = Header(None)) -> str:
    """Authorization 헤더에서 email 추출"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    token = authorization.split(" ", 1)[1]
    payload = decode_jwt(token)
    return payload["email"]

class BookmarkRequest(BaseModel):
    paper_id: str
    title: str
    summary: str = ""
    link: str = ""
    source: str = "unknown"

# Phase 6: 논문 저장
@router.post("/bookmark")
def save_bookmark(
    request: BookmarkRequest,
    authorization: Optional[str] = Header(None)
):
    """
    논문 저장 (보관함에 추가)
    """
    try:
        user_email = get_email_from_token(authorization)
        result = StorageBoxService.save_bookmark(user_email, request.dict())
        return result
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "저장 실패"
        }

# Discord 전용: GET 방식으로 직접 저장
@router.get("/save_direct")
def save_bookmark_direct(
    email: str,
    paper_id: str,
    title: str,
    link: str = "",
    summary: str = "",
    source: str = "unknown"
):
    """
    Discord의 링크 클릭 시 즉시 저장되는 엔드포인트
    """
    from fastapi.responses import HTMLResponse
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"📥 직접 저장 요청 수신: email={email}, paper_id={paper_id}")
        
        # 만약 summary나 link가 비어있다면 papers 테이블에서 조회를 시도
        if not summary or not link:
            try:
                conn = get_connection()
                cursor = conn.cursor(pymysql.cursors.DictCursor)
                cursor.execute("""
                    SELECT title, summary, abstract FROM papers 
                    WHERE arxiv_id = %s AND user_email = %s
                    LIMIT 1
                """, (paper_id, email))
                paper_info = cursor.fetchone()
                conn.close()
                
                if paper_info:
                    if not title: title = paper_info.get("title")
                    if not summary: summary = paper_info.get("summary") or paper_info.get("abstract")
            except Exception as db_err:
                logger.error(f"⚠️ papers 테이블 조회 실패: {db_err}")

        config = {
            "id": paper_id,
            "title": title or "제목 없음",
            "summary": summary or "",
            "link": link or "",
            "source": source
        }
        result = StorageBoxService.save_bookmark(email, config)
        logger.info(f"💾 저장 결과: {result.get('ok')}, msg={result.get('message')}")
        
        if result.get("ok"):
            html_content = """
            <html>
                <head><title>논문 저장 완료</title></head>
                <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; flex-direction: column; background-color: #f9fafb;">
                    <div style="background: white; padding: 2rem; border-radius: 1rem; shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); text-align: center;">
                        <h1 style="color: #4f46e5; margin-bottom: 1rem;">📥 논문 저장 완료!</h1>
                        <p style="color: #374151;">내 보관함에 성공적으로 저장되었습니다.</p>
                        <p style="color: #6b7280; font-size: 0.875rem; margin-top: 1.5rem;">이 창은 잠시 후 자동으로 닫힙니다.</p>
                    </div>
                    <script>setTimeout(() => window.close(), 2000);</script>
                </body>
            </html>
            """
            return HTMLResponse(content=html_content)
        else:
            logger.error(f"❌ 저장 실패: {result.get('error')}")
            return HTMLResponse(content=f"<h1>저장 실패</h1><p>{result.get('message')}</p><p>{result.get('error')}</p>")
    except Exception as e:
        logger.exception("🔥 직접 저장 중 예외 발생")
        return HTMLResponse(content=f"<h1>오류 발생</h1><p>{str(e)}</p>")

# Phase 6: 보관함 조회
@router.get("/bookmarks")
def get_bookmarks(authorization: Optional[str] = Header(None)):
    """
    저장한 논문 목록 조회
    """
    try:
        user_email = get_email_from_token(authorization)
        result = StorageBoxService.get_bookmarks(user_email)
        return result
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "조회 실패"
        }

# Phase 6: 보관함 항목 삭제
@router.delete("/bookmark/{bookmark_id}")
def delete_bookmark(
    bookmark_id: int,
    authorization: Optional[str] = Header(None)
):
    """
    저장한 논문 제거
    """
    try:
        user_email = get_email_from_token(authorization)
        result = StorageBoxService.delete_bookmark(bookmark_id, user_email)
        return result
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": "삭제 실패"
        }
