# email_module/service.py — SMTP 이메일 발송 서비스
import smtplib
import os
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

CODE_EXPIRES_MINUTES = int(os.getenv("AUTH_CODE_EXPIRES_MINUTES", 10))
RESEND_LOCK_SECONDS = int(os.getenv("AUTH_CODE_RESEND_LOCK_SECONDS", 60))
MAX_ATTEMPTS = int(os.getenv("AUTH_CODE_MAX_ATTEMPTS", 5))


def _make_code() -> str:
    return "".join(random.choices(string.digits, k=6))


def _send_mail(to: str, subject: str, html: str, text: str = "") -> dict:
    """실제 SMTP 발송 함수"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        if text:
            msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        if SMTP_SECURE:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.ehlo()
            server.starttls()

        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [to], msg.as_bytes())
        server.quit()
        return {"ok": True}
    except Exception as e:
        print(f"[EmailService] 메일 발송 실패: {e}")
        return {"ok": False, "error": str(e)}


# ─── OTP 인증 코드 발송 ───────────────────────────────────────────────────────

def send_auth_code(to_email: str) -> dict:
    """
    인증 코드 생성 및 DB 저장 + 이메일 발송
    """
    from database import get_connection
    import pymysql

    code = _make_code()
    expire_at = datetime.now() + timedelta(minutes=CODE_EXPIRES_MINUTES)

    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 재전송 잠금 확인
        cursor.execute(
            "SELECT auth_code_sent_at, auth_code_locked_until FROM user_email_auth WHERE email = %s",
            (to_email,)
        )
        existing = cursor.fetchone()

        if existing:
            locked_until = existing.get("auth_code_locked_until")
            if locked_until and locked_until > datetime.now():
                conn.close()
                return {"ok": False, "message": "입력 횟수가 초과되어 잠시 후 다시 시도해주세요."}

            sent_at = existing.get("auth_code_sent_at")
            if sent_at:
                elapsed = (datetime.now() - sent_at).total_seconds()
                if elapsed < RESEND_LOCK_SECONDS:
                    retry_after = int(RESEND_LOCK_SECONDS - elapsed)
                    conn.close()
                    return {
                        "ok": False,
                        "message": f"재전송은 {retry_after}초 후에 가능합니다.",
                        "retryAfterSeconds": retry_after,
                    }

        # upsert
        cursor.execute("""
            INSERT INTO user_email_auth
                (email, auth_code, auth_code_expire, auth_code_attempts, auth_code_sent_at, is_verified)
            VALUES (%s, %s, %s, 0, NOW(), FALSE)
            ON DUPLICATE KEY UPDATE
                auth_code = VALUES(auth_code),
                auth_code_expire = VALUES(auth_code_expire),
                auth_code_attempts = 0,
                auth_code_sent_at = NOW(),
                auth_code_locked_until = NULL,
                is_verified = FALSE
        """, (to_email, code, expire_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[EmailService] DB 저장 실패: {e}")
        return {"ok": False, "error": str(e), "message": "인증 코드 저장 실패"}

    # 이메일 발송
    subject = "[Paper Agent] 이메일 인증 코드"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; background: #f9fafb; border-radius: 12px;">
      <h2 style="color: #111827; font-size: 20px; margin-bottom: 8px;">이메일 인증</h2>
      <p style="color: #6b7280; font-size: 14px; margin-bottom: 24px;">아래 6자리 인증 코드를 입력해주세요. 코드는 {CODE_EXPIRES_MINUTES}분간 유효합니다.</p>
      <div style="background: #111827; color: #f9fafb; font-size: 32px; font-weight: 700; letter-spacing: 8px; text-align: center; padding: 24px; border-radius: 8px; margin-bottom: 24px;">
        {code}
      </div>
      <p style="color: #9ca3af; font-size: 12px;">본인이 요청하지 않았다면 이 이메일을 무시하세요.</p>
    </div>
    """
    text = f"Paper Agent 인증 코드: {code} (유효시간: {CODE_EXPIRES_MINUTES}분)"
    return _send_mail(to_email, subject, html, text)


def verify_auth_code(email: str, code: str) -> dict:
    """
    인증 코드 검증 — 성공 시 users 테이블에 저장
    """
    from database import get_connection, save_user
    import pymysql

    try:
        conn = get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute(
            "SELECT * FROM user_email_auth WHERE email = %s",
            (email,)
        )
        auth = cursor.fetchone()

        if not auth:
            conn.close()
            return {"ok": False, "message": "먼저 인증번호를 요청해주세요.", "type": "send_fail"}

        locked_until = auth.get("auth_code_locked_until")
        if locked_until and locked_until > datetime.now():
            conn.close()
            return {"ok": False, "message": "입력 횟수가 초과되어 잠시 후 다시 시도해주세요.", "type": "locked"}

        expire = auth.get("auth_code_expire")
        if not expire or expire < datetime.now():
            conn.close()
            return {"ok": False, "message": "인증 코드가 만료되었습니다. 다시 요청해주세요.", "type": "expired"}

        if str(auth.get("auth_code", "")).strip() != str(code).strip():
            next_attempts = int(auth.get("auth_code_attempts") or 0) + 1
            lock_until = None
            if next_attempts >= MAX_ATTEMPTS:
                lock_until = datetime.now() + timedelta(minutes=10)

            cursor.execute("""
                UPDATE user_email_auth
                SET auth_code_attempts = %s, auth_code_locked_until = %s
                WHERE email = %s
            """, (next_attempts, lock_until, email))
            conn.commit()
            conn.close()

            remaining = max(MAX_ATTEMPTS - next_attempts, 0)
            if lock_until:
                return {"ok": False, "message": "인증번호를 여러 번 틀렸습니다. 10분 후 다시 시도해주세요.", "type": "locked", "remainingAttempts": 0}
            return {"ok": False, "message": f"인증 코드가 일치하지 않습니다. ({remaining}회 남음)", "type": "wrong", "remainingAttempts": remaining}

        # 인증 성공
        cursor.execute("""
            UPDATE user_email_auth SET is_verified = TRUE, auth_code_attempts = 0,
            auth_code_locked_until = NULL WHERE email = %s
        """, (email,))
        conn.commit()
        conn.close()

        # users 테이블에 저장 (이메일 로그인 사용자)
        save_user(email=email, name=email.split("@")[0], picture="")

        return {"ok": True, "email": email}

    except Exception as e:
        return {"ok": False, "error": str(e), "message": "인증 확인 실패"}


# ─── 테스트 알림 발송 ─────────────────────────────────────────────────────────

def send_test_notification(to_email: str) -> dict:
    """테스트 알림 이메일 발송"""
    subject = "[Paper Agent] 이메일 알림 테스트"
    html = """
    <div style="font-family: -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; background: #f9fafb; border-radius: 12px;">
      <h2 style="color: #111827; font-size: 20px; margin-bottom: 8px;">✅ 이메일 알림 테스트</h2>
      <p style="color: #6b7280; font-size: 14px; margin-bottom: 16px;">Paper Agent 이메일 알림이 정상적으로 연결되었습니다!</p>
      <p style="color: #374151; font-size: 13px;">설정하신 키워드에 맞는 논문이 수집되면 이 이메일 주소로 알림을 보내드립니다.</p>
    </div>
    """
    text = "Paper Agent 이메일 알림 테스트입니다. 정상적으로 연결되었습니다."
    return _send_mail(to_email, subject, html, text)


# ─── 논문 알림 발송 ───────────────────────────────────────────────────────────

def send_papers_email(to_email: str, papers: List[dict], user_email: str = None) -> dict:
    """논문 목록을 이메일로 발송"""
    if not papers:
        return {"ok": True, "message": "발송할 논문이 없습니다.", "papers_count": 0}

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    papers_html = ""
    for i, p in enumerate(papers[:10], 1):
        paper_id = p.get("id") or p.get("arxiv_id") or p.get("paperId", "")
        title = p.get("title", "제목 없음")
        
        # 한국어 초록 또는 본문 요약을 우선적으로 사용
        summary = p.get("body_summary") or p.get("abstract_ko") or p.get("summary") or p.get("abstract", "")
        
        link = p.get("link") or p.get("url", "#")
        authors = p.get("authors", "")
        if isinstance(authors, list):
            authors = ", ".join(authors[:3])
        source = p.get("source", "")
        published = str(p.get("published") or p.get("year") or "")[:10]
        
        import urllib.parse
        encoded_title = urllib.parse.quote(title)
        encoded_authors = urllib.parse.quote(authors)
        citations = p.get("citationCount") or p.get("citations") or 0
        bookmark_link = f"{frontend_url}/bookmark?id={paper_id}&title={encoded_title}&summary={urllib.parse.quote(summary)}&link={urllib.parse.quote(link)}&source={urllib.parse.quote(source)}&authors={encoded_authors}&citations={citations}"

        papers_html += f"""
        <div style="margin-bottom: 24px; padding: 20px; background: white; border-radius: 8px; border: 1px solid #e5e7eb;">
          <h3 style="margin: 0 0 8px; font-size: 15px; color: #111827;">
            <a href="{link}" style="color: #4f46e5; text-decoration: none;">{i}. {title}</a>
          </h3>
          <p style="margin: 0 0 8px; font-size: 12px; color: #6b7280;">{authors} · {published} · {source}</p>
          <p style="margin: 0 0 16px; font-size: 13px; color: #374151; line-height: 1.6; white-space: pre-wrap;">{summary}</p>
          <a href="{bookmark_link}" style="display: inline-block; padding: 8px 16px; background-color: #f3f4f6; color: #374151; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 500; border: 1px solid #d1d5db;">🔖 북마크 저장</a>
        </div>
        """

    subject = f"[Paper Agent] 논문 {len(papers)}개 수집 완료"
    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px 24px; background: #f9fafb;">
      <h2 style="color: #111827; font-size: 20px; margin-bottom: 4px;">📚 새 논문 {len(papers)}개가 수집되었습니다</h2>
      <p style="color: #6b7280; font-size: 14px; margin-bottom: 24px;">Paper Agent 자동 수집 결과</p>
      {papers_html}
      <p style="color: #9ca3af; font-size: 12px; margin-top: 24px;">Paper Agent에서 자동 발송된 메일입니다.</p>
    </div>
    """
    text = f"Paper Agent 논문 수집 완료: {len(papers)}개\n\n" + "\n\n".join(
        [f"{i+1}. {p.get('title','')} - {p.get('link','')}" for i, p in enumerate(papers[:10])]
    )
    return _send_mail(to_email, subject, html, text)
