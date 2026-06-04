from database import get_connection
import pymysql
import json

conn = get_connection()
cursor = conn.cursor(pymysql.cursors.DictCursor)

# 가장 최근 agent_config 조회
cursor.execute("""
    SELECT * FROM agent_configs 
    WHERE user_email = 'lsm4080610@gmail.com'
    ORDER BY updated_at DESC LIMIT 1
""")
agent_config = cursor.fetchone()

if agent_config:
    print('=== 최근 agent_config ===')
    print(f"ID: {agent_config['id']}")
    print(f"Keywords: {agent_config['keywords']}")
    print(f"Sources: {agent_config['sources']}")
    print(f"Configured: {agent_config['is_configured']}")
    
    # 수집된 논문 조회
    cursor.execute("""
        SELECT id, title, source, collected_at FROM papers 
        WHERE user_email = 'lsm4080610@gmail.com'
        ORDER BY collected_at DESC LIMIT 5
    """)
    papers = cursor.fetchall()
    
    if papers:
        print(f'\n=== 수집된 논문 ({len(papers)}개) ===')
        for paper in papers:
            print(f"- {paper['title'][:60]}...")
            print(f"  Source: {paper['source']}, Collected: {paper['collected_at']}")
    else:
        print('\n=== 수집된 논문 없음 ===')

conn.close()
