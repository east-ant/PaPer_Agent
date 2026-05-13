# PPA (Paper Agent) — Frontend

arXiv 등 학술 논문을 키워드 기반으로 자동 수집하고, AI 요약 후 Discord/Slack으로 알림을 보내는 서비스

---

## 기술 스택

| 항목 | 버전 |
|---|---|
| React | 19 |
| Vite | 8 |
| Tailwind CSS | v4 |
| React Router | v7 |
| Zustand | — |

---

## 실행 방법

```bash
npm install
npm run dev      # 개발 서버 (localhost:5173)
npm run build    # 프로덕션 빌드
```

---

## 라우터 구조

| 경로 | 페이지 | 인증 필요 |
|---|---|---|
| `/login` | 로그인 |
| `/loading` | 로딩 전환 화면 | 
| `/dashboard` | 통합 논문 목록 | 
| `/dashboard?tab=popular` | 인기/신규 논문 | 
| `/dashboard?tab=archive` | 내 보관함 | 
| `/agent` | 에이전트 설정 (5단계 stepper) |
| `/agent/status` | 에이전트 현황 |
| `/profile` | 내 정보 | 

> 인증 방식: `localStorage.getItem('ppa_logged_in') === 'true'`
> 백엔드 연결 시 JWT 토큰 검증으로 교체 필요

---

## 상태 관리 (Zustand)

### 1. agentStore — 에이전트 설정 (`localStorage: 'ppa-agent-store'`)

```ts
type Agent = {
  keywords:      string[]            // 최대 5개
  sources:       string[]            // 'arxiv' | 'crossref' | 'semantic' | 'core'
  language:      'ko' | 'en' | 'all'
  summaryLength: 'short' | 'medium' | 'full'
  collectCount:  1 | 3 | 5 | 10
  frequency:     'daily' | '3days' | 'weekly'
  isConfigured:  boolean
  isActive:      boolean
  notifications: {
    discord: { connected: boolean, lastTestStatus: 'success' | 'fail' | null, lastTestAt: number | null }
    slack:   { connected: boolean, lastTestStatus: 'success' | 'fail' | null, lastTestAt: number | null }
  }
}
```

| 함수 | 역할 |
|---|---|
| `setAgent(partial)` | 에이전트 필드 업데이트 |
| `connectNotification(channel)` | Discord/Slack 연결 처리 (현재 mock) |
| `disconnectNotification(channel)` | 연결 해제 |
| `testNotification(channel)` | 테스트 알림 전송 (현재 mock) |
| `resetAgent()` | 초기화 |

### 2. bookmarkStore — 북마크 (`localStorage: 'ppa-bookmarks'`)

```ts
bookmarks: number[]   // paper.id 배열
toggleBookmark(id: number): void
```

---

## 에이전트 상태 로직

```ts
// src/utils/agentStatus.ts
function getAgentStatus(agent): 'unset' | 'active' | 'paused' {
  if (!agent.isConfigured || agent.keywords.length === 0) return 'unset'
  const hasNotification = agent.notifications.discord.connected
                       || agent.notifications.slack.connected
  if (!agent.isActive || !hasNotification) return 'paused'
  return 'active'
}
```

| 상태 | 조건 |
|---|---|
| `unset` | keywords 없음 또는 isConfigured = false |
| `active` | isConfigured && isActive && 알림 1개 이상 연결 |
| `paused` | isConfigured이지만 isActive = false 또는 알림 미연결 |

---

## 백엔드 연결이 필요한 지점

### 인증

```
현재: localStorage 'ppa_logged_in' = 'true' 하드코딩
필요: POST /auth/login  → JWT 발급
      GET  /auth/me     → 유저 정보 반환
```

### 논문 데이터

```
현재: src/data/mock.js 정적 데이터 (10개)
필요: GET /papers?keywords=...&page=...
```

응답 논문 객체 구조:

```ts
{
  id:          number
  title:       string
  authors:     string[]
  publishedAt: string   // 'YYYY.MM.DD'
  collectedAt: string   // 'YYYY.MM.DD'
  journal:     string
  citations:   string   // '1,204' 형식 (콤마 포함 문자열)
  keywords:    string[]
  summary:     string
  url:         string
  growth:      number   // 7일 기준 인용 증가율 (인기 탭 정렬용)
  daysAgo:     number   // 수집일 기준 며칠 전 (신규 탭 필터용)
}
```

### 통계

```
현재: src/data/mock.js mockStats 하드코딩
필요: GET /stats

응답 구조:
{
  totalPapers:  number
  weeklyAdded:  number
  weeklyGrowth: string      // '+12%'
  updatedAt:    string      // '오전 9:00시 업데이트'
  topKeywords:  { label: string, count: number }[]
  trend:        number[]    // 최근 12주 수집량
  trendLabels:  string[]    // ['3/25', '4/1', ...]
}
```

### 알림 연동 (OAuth)

```
현재: connectNotification() → connected: true 즉시 세팅 (mock)
필요: OAuth 팝업 → 백엔드 callback → connected 상태 반영

Discord: OAuth2 Bot 권한 방식
Slack:   OAuth2 방식
Webhook 방식 미사용 — OAuth만 사용
```

### 에이전트 설정 저장

```
현재: Zustand localStorage에만 저장
필요: POST /agent  → 서버 저장 + 수집 스케줄러 등록
      GET  /agent  → 저장된 설정 불러오기 (앱 초기 로딩 시)
```

---

## 소스 ID 매핑

| ID | 표시명 |
|---|---|
| `arxiv` | arXiv |
| `crossref` | Crossref |
| `semantic` | Semantic Scholar |
| `core` | CORE |

> 국내 소스는 현재 준비중 처리됨

---

## 프로젝트 구조

```
src/
├── pages/
│   ├── LoginPage.jsx          # 로그인
│   ├── DashboardPage.jsx      # 통합/인기/보관함 탭
│   ├── AgentSetupPage.jsx     # 에이전트 5단계 설정
│   ├── AgentStatusPage.jsx    # 에이전트 현황
│   ├── ProfilePage.jsx        # 내 정보
│   └── LoadingPage.jsx        # 설정 저장 후 전환 화면
├── components/
│   ├── layout/Sidebar.jsx     # 사이드바 네비게이션
│   ├── layout/Topbar.jsx      # 탭 네비 + 에이전트 상태 pill
│   └── stepper/AgentStepper.jsx  # 설정 stepper (5단계)
├── store/
│   ├── agentStore.js          # 에이전트 상태
│   └── bookmarkStore.js       # 북마크 상태
├── utils/
│   └── agentStatus.js         # 상태 계산 유틸
└── data/
    └── mock.js                # 임시 데이터 (백엔드 연결 시 삭제)
```

---

## 환경 변수 (백엔드 연결 시 추가 필요)

```env
VITE_API_BASE_URL=https://api.ppa.dev
VITE_DISCORD_CLIENT_ID=...
VITE_SLACK_CLIENT_ID=...
```

---

## 구현된 주요 기능

### 페이지

| 페이지 | 주요 기능 |
|---|---|
| 로그인 | Google OAuth 연동 버튼, 로딩 전환 |
| 대시보드 — 통합 | KPI 카드 3개, 수집 트렌드 차트 (주별/월별/년별), 최신 논문 목록 |
| 대시보드 — 인기/신규 | 급상승 논문 TOP3, 기간 필터(1일/3일/7일) 신규 수집 목록 |
| 대시보드 — 내 보관함 | 북마크 목록, 최신순/인용순 정렬 |
| 에이전트 설정 | 5단계 stepper (키워드 → 소스 → 요약범위 → 알림 → 요약확인) |
| 에이전트 현황 | 상태 표시, 활성/일시정지 토글, 설정 요약, 알림 채널 연결 상태 |
| 내 정보 | 프로필 카드, 계정 정보, 연동 상태, 로그아웃 |

### 공통 컴포넌트

- **Sidebar** — 접기/펼치기 토글, 네비게이션, 로그아웃
- **Topbar** — 탭 네비게이션(대시보드), 에이전트 상태 pill, hover 시 Discord/Slack 연결 상태 popover
- **스켈레톤 shimmer** — 데이터 로딩 중 플레이스홀더 UI
- **북마크 버튼** — hover 시 표시, 저장된 항목은 항상 표시, 보관함 연동

---

## 업데이트 내역

### 2026-05-12

#### 새로 추가된 기능
- 대시보드에 논문 수집 트렌드 그래프 추가 (주별 / 월별 / 연별로 전환 가능)
- 대시보드 수치 카드 디자인 개선 (총 수집 수, 키워드 수, 마지막 수집 시각을 한눈에 확인)
- 에이전트 설정 저장 시 로딩 화면에서 단계별 진행 문구 순차 표시 ("키워드 분석 중 → 최신 논문 찾는 중 → 요약 준비 중")
- 에이전트 설정 화면에서 각 수집 소스(arXiv 등)에 한국어 설명 툴팁 추가
- 에이전트 현황 페이지에 활성화 / 일시정지 토글 버튼 추가 (알림 채널 미연결 시 비활성화)
- 에이전트가 일시정지 상태일 때 원인과 해결 방법 안내 박스 표시
- 북마크 전체 초기화 기능 추가 (로그아웃 시 자동 적용)
- 백엔드 연결을 위한 API 호출 파일 구조 사전 준비 (auth / papers / agent)

#### 디자인 개선
- 에이전트 일시정지 안내 박스 색상을 빨간색 → 주황색으로 변경 (위급한 느낌 완화)
- 상단 바의 에이전트 상태 표시에 깜빡이는 효과 추가, 호버 시 Discord/Slack 연결 상태 확인 가능
- 왼쪽 사이드바에서 현재 보고 있는 메뉴 항목에 강조 바(accent bar) 표시

#### 버그 수정
- 에이전트 설정 중 취소 버튼을 눌러도 변경사항이 남아있던 문제 수정 (취소 시 이전 상태로 완전 복원)
- 알림 채널 연결 후 연결 버튼을 다시 누를 수 있던 문제 수정
- 대시보드 그래프 데이터가 수치 카드와 맞지 않던 문제 수정
- 로그아웃 시 에이전트 설정과 북마크가 초기화되지 않던 문제 수정
- 에이전트 현황 페이지에서 상태에 맞지 않는 버튼 문구가 표시되던 문제 수정 (활성 상태일 때만 "일시정지" 표시)
