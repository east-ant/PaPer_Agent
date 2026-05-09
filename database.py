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
        CREATE TABLE IF NOT EXISTS papers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            arxiv_id VARCHAR(50) UNIQUE,
            title VARCHAR(500),
            abstract TEXT,
            summary TEXT,
            category VARCHAR(50),
            published DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) UNIQUE,
            name VARCHAR(255),
            picture VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
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