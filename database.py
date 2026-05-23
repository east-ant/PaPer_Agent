import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4"
    )

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE,
            name VARCHAR(255),
            picture VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 기존 테이블 (원본 유지)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            arxiv_id VARCHAR(50) UNIQUE,
            title VARCHAR(500),
            abstract TEXT,
            summary TEXT,
            category VARCHAR(50),
            published DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    
    # Phase 0-1: 신규 테이블
    # 에이전트 설정 (사용자당 1개)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_configs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255) UNIQUE,
            keywords JSON,
            sources JSON,
            language VARCHAR(10) DEFAULT 'ko',
            summary_length VARCHAR(20) DEFAULT 'medium',
            collect_count INT DEFAULT 5,
            frequency VARCHAR(20) DEFAULT 'daily',
            is_active BOOLEAN DEFAULT FALSE,
            is_configured BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 알림 설정 (Discord 토큰, 연결 상태)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            discord_user_id VARCHAR(255),
            discord_username VARCHAR(255),
            discord_guild_id VARCHAR(255),
            discord_channel_id VARCHAR(255),
            discord_webhook_url TEXT,
            discord_access_token TEXT,
            discord_refresh_token TEXT,
            discord_token_expires_at DATETIME,
            last_discord_test_status VARCHAR(20),
            last_discord_test_at DATETIME,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email),
            INDEX idx_user_email (user_email)
        )
    """)
    
    # 발송 기록 (즉시 발송, 정시 발송, 테스트)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            notification_settings_id INT,
            user_email VARCHAR(255),
            papers_count INT DEFAULT 0,
            alert_type VARCHAR(20) DEFAULT 'scheduled',
            status VARCHAR(20) DEFAULT 'success',
            error_message TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (notification_settings_id) REFERENCES notification_settings(id) ON DELETE CASCADE,
            FOREIGN KEY (user_email) REFERENCES users(email),
            INDEX idx_sent_at (sent_at),
            INDEX idx_user_email (user_email)
        )
    """)
    
    # 보관함 (저장한 논문)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            paper_id VARCHAR(255),
            title VARCHAR(500),
            summary TEXT,
            link TEXT,
            source VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email),
            INDEX idx_user_email (user_email)
        )
    """)
    
    # 발송된 논문 기록 (중복 발송 방지용)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_email VARCHAR(255),
            paper_id VARCHAR(255),
            title VARCHAR(500),
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_email) REFERENCES users(email),
            INDEX idx_user_paper (user_email, paper_id),
            INDEX idx_user_title (user_email, title(255))
        )
    """)
    
    conn.commit()
    # --- 호환성 마이그레이션: 다른 레포(예: paper_Agent)의 스키마가 적용된 경우 대비 ---
    try:
        # notification_settings에 user_email이 없고 user_id가 있으면 user_email 추가
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'notification_settings'
              AND column_name = 'user_email'
        """)
        has_user_email = cursor.fetchone()[0] > 0

        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'notification_settings'
              AND column_name = 'user_id'
        """)
        has_user_id = cursor.fetchone()[0] > 0

        if not has_user_email and has_user_id:
            # user_email 컬럼 추가 (nullable temporarily)
            cursor.execute("ALTER TABLE notification_settings ADD COLUMN user_email VARCHAR(255) NULL")
            # 기존 user_id 값이 이메일(또는 식별자)로 사용되었다면 복사
            cursor.execute("UPDATE notification_settings SET user_email = user_id")
            # 이제 NOT NULL/외래키가 필요하면 별도 마이그레이션으로 처리

        # scheduled_alerts: user_email 컬럼이 없고 bookmarks 등에서 user_id가 있으면 추가
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'scheduled_alerts'
              AND column_name = 'user_email'
        """)
        has_sa_user_email = cursor.fetchone()[0] > 0

        if not has_sa_user_email:
            cursor.execute("ALTER TABLE scheduled_alerts ADD COLUMN user_email VARCHAR(255) NULL")
            # 가능한 경우 notification_settings 테이블과 조인해 채움
            try:
                cursor.execute("""
                    UPDATE scheduled_alerts sa
                    JOIN notification_settings ns ON sa.notification_settings_id = ns.id
                    SET sa.user_email = ns.user_email
                    WHERE sa.user_email IS NULL
                """)
            except Exception:
                pass

        # bookmarks: add user_email from user_id if needed
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'bookmarks'
              AND column_name = 'user_email'
        """)
        has_bm_user_email = cursor.fetchone()[0] > 0

        if not has_bm_user_email:
            # if bookmarks has user_id, copy to user_email
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'bookmarks'
                  AND column_name = 'user_id'
            """)
            has_bm_user_id = cursor.fetchone()[0] > 0
            if has_bm_user_id:
                cursor.execute("ALTER TABLE bookmarks ADD COLUMN user_email VARCHAR(255) NULL")
                cursor.execute("UPDATE bookmarks SET user_email = user_id")

        conn.commit()
    except Exception as e:
        # 마이그레이션 실패는 경고로 남기고 종료
        print(f"DB 마이그레이션 경고: {e}")
    finally:
        conn.close()

def save_user(email: str, name: str, picture: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT IGNORE INTO users (email, name, picture)
            VALUES (%s, %s, %s)
        """, (email, name, picture))
        conn.commit()
        return True
    except Exception as e:
        print(f"유저 저장 실패: {e}")
        return False
    finally:
        conn.close()

def save_paper(arxiv_id: str, title: str, abstract: str, summary: str, user_email: str, category: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT IGNORE INTO papers (user_email, arxiv_id, title, abstract, summary, category)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_email, arxiv_id, title, abstract, summary, category))
        conn.commit()
        return True
    except Exception as e:
        print(f"저장 실패: {e}")
        return False
    finally:
        conn.close()

def get_papers(user_email: str):
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(
        "SELECT * FROM papers WHERE user_email = %s ORDER BY created_at DESC",
        (user_email,)
    )
    result = cursor.fetchall()
    conn.close()
    return result