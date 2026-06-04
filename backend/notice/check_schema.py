from database import get_connection
import pymysql

conn = get_connection()
cursor = conn.cursor(pymysql.cursors.DictCursor)

# agent_configs 스키마 확인
cursor.execute('DESCRIBE agent_configs')
cols = cursor.fetchall()
print('=== agent_configs 스키마 ===')
for col in cols:
    print(f"{col['Field']}: {col['Type']}")

# notification_settings 스키마 확인
cursor.execute('DESCRIBE notification_settings')
cols = cursor.fetchall()
print('\n=== notification_settings 스키마 ===')
for col in cols:
    print(f"{col['Field']}: {col['Type']}")

# agent_configs 최근 데이터 확인
cursor.execute('SELECT * FROM agent_configs ORDER BY created_at DESC LIMIT 1')
result = cursor.fetchone()
print('\n=== agent_configs 최근 데이터 ===')
if result:
    for k, v in result.items():
        print(f'{k}: {v}')
else:
    print('저장된 데이터 없음')

conn.close()
