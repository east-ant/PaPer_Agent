from database import get_connection
import pymysql

conn = get_connection()
cursor = conn.cursor(pymysql.cursors.DictCursor)

# papers 테이블 스키마 확인
cursor.execute('DESCRIBE papers')
cols = cursor.fetchall()
print('=== papers 테이블 스키마 ===')
for col in cols:
    print(f"{col['Field']}: {col['Type']}")

# 가장 최근 papers 조회
cursor.execute('SELECT COUNT(*) as count FROM papers WHERE user_email = "lsm4080610@gmail.com"')
result = cursor.fetchone()
print(f'\n=== 수집된 논문 수: {result["count"]} ===')

if result['count'] > 0:
    cursor.execute("""
        SELECT id, title, collected_at FROM papers 
        WHERE user_email = 'lsm4080610@gmail.com'
        ORDER BY collected_at DESC LIMIT 3
    """)
    papers = cursor.fetchall()
    for paper in papers:
        print(f"- {paper['title'][:60]}...")
        print(f"  Collected: {paper['collected_at']}")

conn.close()
