# 📄 PaPer Agent (PPA)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-B73BFE?style=flat-square&logo=vite&logoColor=FFD62E)](https://vitejs.dev/)

**PaPer Agent**는 학술 논문을 사용자가 설정한 키워드 기반으로 자동 수집하고, AI를 이용해 한국어로 요약 및 번역하여 제공하는 지능형 에이전트 서비스입니다. 
매일 쏟아지는 수많은 논문 속에서 필요한 정보만 필터링하고, **Discord, Slack, 이메일**을 통해 편리하게 요약 알림을 받아볼 수 있습니다.

---

## ✨ 주요 기능

* 🔍 **다중 소스 논문 수집**: arXiv, Crossref, Semantic Scholar, CORE 등 주요 학술 데이터베이스를 통합 검색 및 수집합니다.
* 🤖 **AI 요약 및 번역 (GPT 연동)**: 수집된 논문의 초록을 분석하여 관련성을 평가하고, 핵심 내용을 한국어로 요약해 제공합니다.
* 🔔 **맞춤형 멀티 채널 알림**: 수집된 논문 정보를 Discord, Slack, 이메일 등 원하는 채널로 자동 발송합니다.
* 📊 **대시보드 인사이트**: 주별/월별 논문 수집 트렌드, 인기 검색 키워드, 최신 논문 등의 통계를 웹 대시보드에서 실시간으로 확인 가능합니다.
* 📑 **북마크 및 보관함**: 알림 이메일에서 바로 논문을 북마크하거나, 웹 대시보드 내 보관함에서 관심 논문을 별도로 관리할 수 있습니다.
* ⚙️ **5단계 에이전트 설정**: 직관적인 UI 마법사를 통해 키워드, 소스, 언어, 요약 길이, 알림 빈도 등을 손쉽게 커스터마이징할 수 있습니다.
* 🔐 **간편한 인증**: Google OAuth 연동 및 이메일 OTP 기반의 안전하고 간편한 로그인/회원가입을 지원합니다.

---

## 🛠 기술 스택

### Frontend
* **Core**: React 19, Vite 8
* **Styling**: Tailwind CSS v4
* **Routing**: React Router v7
* **State Management**: Zustand

### Backend
* **Core**: Python, FastAPI, Uvicorn
* **AI & NLP**: OpenAI GPT API, LangChain
* **DB & ORM**: MySQL, SQLAlchemy
* **Data Processing**: pypdfium2, rapidocr-onnxruntime, numpy, feedparser

---

## 📁 프로젝트 구조

```text
PaPer_Agent/
├── backend/                  # FastAPI 백엔드
│   ├── main.py               # API 라우터 및 서버 엔드포인트
│   ├── agent.py              # LangChain & GPT 기반 문서 요약 / 번역 에이전트
│   ├── api_get.py            # 외부 API 연동 논문 수집 모듈
│   ├── database.py           # DB 연결 및 쿼리 처리
│   ├── auth.py               # 인증 및 JWT 토큰 관리
│   ├── discord_module/       # Discord 웹훅 연동 모듈
│   └── email_module/         # 이메일 알림/OTP 발송 모듈
│
├── frontend/                 # React 프론트엔드
│   ├── src/
│   │   ├── api/              # 백엔드 API 통신 함수 (agent, papers, auth)
│   │   ├── components/       # 재사용 가능한 UI 컴포넌트 및 에러 바운더리
│   │   ├── pages/            # 페이지 컴포넌트 (대시보드, 에이전트 설정, 로그인 등)
│   │   ├── store/            # Zustand 전역 상태 관리 (agentStore, bookmarkStore)
│   │   └── utils/            # 상태 처리 및 유틸리티 함수
│   └── vite.config.js
└── README.md
```

---

## 🚀 시작하기 (Getting Started)

프로젝트를 로컬 환경에서 실행하는 방법입니다.

### 1. 백엔드 (Backend) 설정

```bash
# 1. 백엔드 디렉토리로 이동
cd backend

# 2. 가상환경 생성 및 활성화
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

# 3. 의존성 패키지 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
# backend/.env 파일을 생성하고 아래 내용을 입력합니다.

SEMANTIC_SCHOLAR_API_KEY=your_semantic_scholar_api_key
OPENAI_API_KEY=your_openai_api_key

# 5. 서버 실행
uvicorn main:app --reload
```
서버가 실행되면 `http://localhost:8000` 에서 접속 가능하며, API 문서(Swagger UI)는 `http://localhost:8000/docs` 에서 확인할 수 있습니다.

### 2. 프론트엔드 (Frontend) 설정

```bash
# 1. 프론트엔드 디렉토리로 이동
cd frontend

# 2. 패키지 설치
npm install

# 3. 환경 변수 설정
# frontend/.env 파일을 생성하고 아래 내용을 입력합니다. (필요 시)
VITE_API_BASE_URL=http://localhost:8000

# 4. 개발 서버 실행
npm run dev
```
웹 브라우저를 열고 `http://localhost:5173` 으로 접속하면 대시보드 화면을 볼 수 있습니다.

---

## 🔗 주요 API 엔드포인트

| HTTP Method | Endpoint | 설명 |
|---|---|---|
| **GET** | `/` | 서버 상태 확인 (Health Check) |
| **POST** | `/search` | 특정 키워드를 기반으로 외부 소스에서 논문 검색 |
| **POST** | `/collect` | 자동 수집 스케줄러 기반 논문 수집 및 DB 저장 |
| **POST** | `/analyze` | LangChain Agent를 통한 논문 관련성 분석 |
| **GET** | `/papers` | 저장된 논문 전체 목록 조회 |
| **POST** | `/paper/pdf` | 특정 논문 PDF 원문 추출 및 한국어 번역 요약 |

자세한 API 스펙은 백엔드 서버 구동 후 `/docs` (Swagger UI)에서 확인 가능합니다.

---

## 📜 라이선스 (License)

이 프로젝트는 [MIT License](https://opensource.org/licenses/MIT)를 따릅니다.
