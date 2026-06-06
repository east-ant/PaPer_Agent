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
    
    # 1. papers 테이블 (사용자 명세 반영)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            arxiv_id VARCHAR(50) UNIQUE,
            title VARCHAR(500),
            abstract TEXT,
            summary TEXT,
            category VARCHAR(50),
            published DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_email VARCHAR(255),
            authors TEXT,
            citations INT DEFAULT 0,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 기존 papers 테이블에 컬럼 추가 (이미 존재하면 무시됨)
    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN authors TEXT")
    except Exception:
        pass
        
    try:
        cursor.execute("ALTER TABLE papers ADD COLUMN citations INT DEFAULT 0")
    except Exception:
        pass
    
    # 2. agent_configs 테이블 (사용자 명세 반영)
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
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 3. notification_settings 테이블 (사용자 명세 반영)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255),
            notification_channel ENUM('discord', 'slack') DEFAULT 'discord',
            channel_id VARCHAR(255),
            webhook_url TEXT,
            keywords JSON,
            sources JSON,
            language VARCHAR(10) DEFAULT 'all',
            summary_length ENUM('short', 'medium', 'full') DEFAULT 'medium',
            frequency ENUM('daily', '3days', 'weekly') DEFAULT 'daily',
            is_active BOOLEAN DEFAULT FALSE,
            last_sent_at TIMESTAMP NULL DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            user_email VARCHAR(255) UNIQUE,
            discord_user_id VARCHAR(255),
            discord_username VARCHAR(255),
            discord_guild_id VARCHAR(255),
            discord_channel_id VARCHAR(255),
            discord_webhook_url TEXT,
            discord_access_token TEXT,
            discord_refresh_token TEXT,
            discord_token_expires_at DATETIME,
            last_discord_test_status VARCHAR(20),
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 4. scheduled_alerts 테이블 (사용자 명세 반영 - alert_type은 마이그레이션으로 추가)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            notification_settings_id INT,
            papers_count INT DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) DEFAULT 'success',
            error_message TEXT,
            user_email VARCHAR(255),
            FOREIGN KEY (notification_settings_id) REFERENCES notification_settings(id) ON DELETE CASCADE,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 5. bookmarks 테이블 (사용자 명세 반영)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            paper_id VARCHAR(255) NOT NULL,
            paper_data JSON,
            bookmarked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_email VARCHAR(255),
            title VARCHAR(500),
            summary TEXT,
            link TEXT,
            source VARCHAR(100),
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    """)
    
    # 6. sent_papers 테이블 (원본 유지)
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

    # 7. user_email_auth 테이블 (사용자 명세 반영)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_email_auth (
            email VARCHAR(255) PRIMARY KEY,
            auth_code VARCHAR(10),
            auth_code_expire DATETIME,
            auth_code_attempts INT DEFAULT 0,
            auth_code_sent_at DATETIME,
            auth_code_locked_until DATETIME,
            is_verified BOOLEAN DEFAULT FALSE
        )
    """)
    
    conn.commit()
    # --- 이메일 알림 컬럼 마이그레이션 ---
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'notification_settings'
              AND column_name = 'email_connected'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE notification_settings ADD COLUMN email_connected BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE notification_settings ADD COLUMN email_address VARCHAR(255)")
            conn.commit()
    except Exception as e:
        print(f"이메일 컬럼 마이그레이션 경고: {e}")
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

        # 4. scheduled_alerts: alert_type 컬럼이 없으면 추가
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'scheduled_alerts'
              AND column_name = 'alert_type'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE scheduled_alerts ADD COLUMN alert_type VARCHAR(20) DEFAULT 'scheduled'")
            
        # 5. agent_configs: updated_at 컬럼이 없으면 추가
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'agent_configs'
              AND column_name = 'updated_at'
        """)
        if cursor.fetchone()[0] == 0:
            cursor.execute("ALTER TABLE agent_configs ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")

        # 6. scheduled_alerts: status enum의 값 확장 마이그레이션
        try:
            cursor.execute("ALTER TABLE scheduled_alerts MODIFY COLUMN status enum('success','failed','sent','pending','test') DEFAULT 'pending'")
        except Exception as enum_err:
            print(f"status enum 확장 실패: {enum_err}")

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
        # 이메일 로그인 시 picture가 ""로 오면 기존 picture(구글 연동된 것)를 덮어쓰지 않도록 함
        if picture:
            cursor.execute("""
                INSERT INTO users (email, name, picture)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                picture = VALUES(picture)
            """, (email, name, picture))
        else:
            cursor.execute("""
                INSERT INTO users (email, name, picture)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                name = VALUES(name)
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

def get_papers(user_email: str = None):
    import datetime
    conn = get_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    # 전체 사용자 논문 조회 (대시보드 전역 통계용)
    cursor.execute(
        "SELECT * FROM papers ORDER BY created_at DESC LIMIT 100"
    )
    result = cursor.fetchall()
    conn.close()
    
    # 프론트엔드 기대 스키마로 포맷 가공 및 날짜 직렬화 처리
    now = datetime.datetime.now()
    for row in result:
        created_at = row.get("created_at")
        if created_at:
            delta = now - created_at
            days_ago = delta.days
            row["daysAgo"] = max(0, days_ago)
            row["created_at"] = created_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            row["daysAgo"] = 0
            row["created_at"] = ""
            
        published = row.get("published")
        if isinstance(published, datetime.datetime):
            row["publishedAt"] = published.strftime("%Y-%m-%d")
            row["published"] = published.strftime("%Y-%m-%d %H:%M:%S")
        elif published:
            row["publishedAt"] = str(published)[:10]
            row["published"] = str(published)
        else:
            row["publishedAt"] = "미상"
            row["published"] = ""
            
        row["paper_id"] = row.get("arxiv_id") or str(row.get("id"))
        row["link"] = row.get("arxiv_id") or ""
        row["url"] = row.get("arxiv_id") or ""
        row["journal"] = row.get("category") or "arXiv"
        row["citations"] = row.get("citations") or 0
        row["growth"] = 0
        authors_val = row.get("authors")
        row["authors"] = [a.strip() for a in authors_val.split(",")] if authors_val else []
        
    return result