# PaPer Agent - Backend

논문 검색 및 AI 요약 서비스의 백엔드입니다.

---

## 설치 및 실행

### 1. 가상환경 생성 및 활성화
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 2. 패키지 설치
```bash
pip install fastapi uvicorn python-dotenv feedparser numpy pypdfium2 rapidocr-onnxruntime requests
```


### 4. 실행
```bash
.\venv\Scripts\activate
uvicorn main:app --reload
```
서버가 `http://localhost:8000` 에서 실행됩니다.

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 서버 상태 확인 |
| POST | `/search` | 키워드로 논문 검색 |
| POST | `/collect` | 논문 수집 후 DB 저장 |
| POST | `/analyze` | 논문 관련성 분석 |
| GET | `/papers` | 저장된 논문 목록 조회 |

### /search 요청 예시
```json
{
  "keyword": "deep learning",
  "limit": 10,
  "withSummary": false
}
```

---

## 동작 방식
POST /search 요청 (키워드)
↓
arXiv, Crossref, Semantic Scholar, CORE 4개 소스에서 논문 수집
↓
중복 제거 및 최신순 정렬
↓
프론트엔드가 기대하는 형식으로 변환 후 반환

POST /collect 요청
↓
4개 소스에서 논문 수집
↓
AI 에이전트가 관련성 판단 (agent.py)
↓
관련 논문만 DB에 저장 (database.py)

---

## 주요 파일 구조
backend/
├── main.py          # FastAPI 서버, 엔드포인트 정의
├── api_down.py      # 논문 수집 (arXiv, Crossref, Semantic Scholar, CORE)
├── agent.py         # AI 관련성 분석
├── database.py      # DB 저장 및 조회
├── config.py        # 환경변수 로드
└── .env             # API 키 설정 (git 제외)

---

## Swagger UI

서버 실행 후 브라우저에서 `http://localhost:8000/docs` 접속하면
API를 직접 테스트할 수 있습니다.