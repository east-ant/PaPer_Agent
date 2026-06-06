# PPA (Paper Agent) — Frontend

arXiv 등 학술 논문을 키워드 기반으로 자동 수집하고, AI 요약 후 Discord/Slack/이메일로 알림을 보내는 서비스

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
npm run lint     # 코드 검사
```

---

## 라우터 구조

| 경로 | 페이지 |
|---|---|
| `/login` | 로그인 (Google OAuth + 이메일 인증) |
| `/loading` | 로딩 전환 화면 |
| `/dashboard` | 통합 논문 목록 |
| `/dashboard?tab=popular` | 인기/신규 논문 |
| `/dashboard?tab=archive` | 내 보관함 |
| `/agent` | 에이전트 설정 (5단계 stepper) |
| `/agent/status` | 에이전트 현황 |
| `/profile` | 내 정보 |
| `*` | 404 페이지 |

---

## 프로젝트 구조

```
src/
├── api/
│   ├── agent.js           # 에이전트 API 진입점 (백엔드 연결 시 여기 수정)
│   ├── papers.js          # 논문 API 진입점 (백엔드 연결 시 여기 수정)
│   ├── auth.js            # 인증 유틸
│   └── mock/
│       ├── agent.mock.js  # 에이전트 mock 구현
│       └── papers.mock.js # 논문 mock 구현
├── pages/
│   ├── LoginPage.jsx          # 로그인
│   ├── DashboardPage.jsx      # 통합/인기/보관함 탭
│   ├── AgentSetupPage.jsx     # 에이전트 5단계 설정
│   ├── AgentStatusPage.jsx    # 에이전트 현황
│   ├── ProfilePage.jsx        # 내 정보
│   ├── LoadingPage.jsx        # 설정 저장 후 전환 화면
│   └── NotFoundPage.jsx       # 404
├── components/
│   ├── ErrorBoundary.jsx      # 에러 바운더리
│   ├── layout/Sidebar.jsx     # 사이드바 네비게이션
│   ├── layout/Topbar.jsx      # 탭 네비 + 에이전트 상태 pill
│   └── stepper/AgentStepper.jsx  # 설정 stepper (5단계)
├── store/
│   ├── agentStore.js          # 에이전트 상태
│   └── bookmarkStore.js       # 북마크 상태
├── utils/
│   ├── agentStatus.js         # 상태 계산 유틸
│   └── auth.js                # 로그인/로그아웃 유틸
└── data/
    └── mock.js                # 임시 논문/통계 데이터
```

---

## API 파일 구조 설명

`src/api/agent.js`, `src/api/papers.js` 두 파일이 백엔드 연결의 진입점이야.

지금은 각 함수 안에서 mock 데이터를 쓰고 있어. 백엔드 연결할 때 이 파일 안의 함수 내부만 실제 fetch 코드로 바꾸면 돼. 다른 파일(pages, store, components)은 건드릴 필요 없어.

mock 데이터는 `src/api/mock/` 폴더에서 분리해서 관리하고 있어.

**주의:** pages, components, store에서 mock 파일을 직접 import하면 안 돼. 반드시 `api/agent.js`, `api/papers.js`를 통해서만 써야 해. `npm run build`에서 자동으로 체크함.

---

## 상태 관리 (Zustand)

### agentStore — 에이전트 설정 (`localStorage: 'ppa-agent-store'`)

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
    email:   { connected: boolean, lastTestStatus: 'success' | 'fail' | null, lastTestAt: number | null }
  }
}
```

### bookmarkStore — 북마크 (`localStorage: 'ppa-bookmarks'`)

```ts
bookmarks: number[]
toggleBookmark(id: number): void
```

---

## 에이전트 상태 로직

```ts
// src/utils/agentStatus.js
function getAgentStatus(agent): 'unset' | 'active' | 'paused' {
  if (!agent.isConfigured || agent.keywords.length === 0) return 'unset'
  const hasNotification =
    agent.notifications?.discord?.connected ||
    agent.notifications?.slack?.connected ||
    agent.notifications?.email?.connected
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

## 환경 변수

```env
VITE_API_BASE_URL=https://paper-agent-altv.onrender.com
```

---

## 업데이트 내역

### 2026-06-02

#### 새로 추가된 기능
- 로그인 페이지에 이메일 인증 플로우 추가 (이메일 입력 → 인증코드 발송 → 확인)
- 에이전트 알림 채널에 이메일 추가 (Discord, Slack, 이메일)
- 404 페이지 추가 (존재하지 않는 경로 접근 시)
- 에러 바운더리 추가 (JS 오류 발생 시 앱 전체가 죽지 않게 처리)
- 로그인 만료 처리 유틸 추가 (`clearAuth`, `isLoggedIn`)
- API 파일 구조 정리 (agent.js, papers.js를 진입점으로, mock은 mock/ 폴더로 분리)
- boundary 체크 스크립트 추가 (빌드/린트 시 mock 직접 import 자동 감지)

#### 버그 수정
- `/agent` 페이지에서 추천 키워드 클릭 또는 다음 버튼 누를 때 빈화면 뜨는 문제 수정 (animate-fade-up 재실행 문제)
- 내정보 페이지에서 백엔드 서버가 느릴 때 "불러오는 중"에서 멈추는 문제 수정 (4초 타임아웃 + 기본 정보 fallback)
- 로그아웃 시 ppa_token이 삭제되지 않던 문제 수정
- notifications optional chaining 누락으로 인한 crash 가능성 수정
- AgentStepper 취소 시 이메일 알림 상태가 원복되지 않던 문제 수정
- AuthCallbackPage useEffect dependency 누락 수정

### 2026-05-12

#### 새로 추가된 기능
- 대시보드에 논문 수집 트렌드 그래프 추가 (주별 / 월별 / 연별로 전환 가능)
- 대시보드 수치 카드 디자인 개선
- 에이전트 설정 저장 시 로딩 화면에서 단계별 진행 문구 순차 표시
- 에이전트 설정 화면에서 각 수집 소스에 한국어 설명 툴팁 추가
- 에이전트 현황 페이지에 활성화 / 일시정지 토글 버튼 추가
- 에이전트가 일시정지 상태일 때 원인과 해결 방법 안내 박스 표시
- 북마크 전체 초기화 기능 추가 (로그아웃 시 자동 적용)

#### 디자인 개선
- 에이전트 일시정지 안내 박스 색상을 빨간색 → 주황색으로 변경
- 상단 바의 에이전트 상태 표시에 깜빡이는 효과 추가, 호버 시 연결 상태 확인 가능
- 왼쪽 사이드바에서 현재 보고 있는 메뉴 항목에 강조 바 표시

#### 버그 수정
- 에이전트 설정 중 취소 버튼을 눌러도 변경사항이 남아있던 문제 수정
- 알림 채널 연결 후 연결 버튼을 다시 누를 수 있던 문제 수정
- 대시보드 그래프 데이터가 수치 카드와 맞지 않던 문제 수정
- 로그아웃 시 에이전트 설정과 북마크가 초기화되지 않던 문제 수정

### 2026-06-06

#### 새로 추가된 기능
- 디스코드 알림 메시지에 인용 수, 저자명, 발행일 정보 표시 추가 (발행일 위, 저자 오른쪽 위치)
- 논문 수집 시, 영어 원문 대신 에이전트가 번역한 한국어 요약본(`abstract_ko`)을 DB에 저장하여 대시보드 및 알림에서 한글로 일관성 있게 표시되도록 구조 개선
- DB `papers` 테이블에 `authors`, `citations` 컬럼을 신규 추가하여, 대시보드 및 북마크(내 보관함)에서 저자명과 인용 수를 정확히 표기하도록 연동

#### 디자인 및 사용성 개선
- 대시보드 통합창의 최신 논문 표시 개수를 1개에서 2개로 고정 및 UI 문구 변경
- 대시보드의 '인기 키워드 TOP 3' 집계 방식을 단순 카테고리가 아닌, 사용자가 `agent_configs`에 직접 등록한 실제 검색 키워드 기반으로 집계하도록 개선
- 시스템의 중복 수집 방지 특성에 맞춰, 불필요해진 대시보드의 '이번 주 급상승(수집 증가율 기준)' UI 섹션 완전 삭제

#### 버그 수정
- Semantic Scholar API 수집 시 `publicationDate` 필드를 추가 호출하여, 일부 논문에서 발행일(년도)을 정상적으로 가져오지 못하던 파싱 에러 수정
- 대시보드 인기/신규 창의 '신규 수집' 탭에서 1일/3일/7일 필터링이 동작하지 않던 문제 해결 (프론트엔드 `daysAgo` 데이터 매핑 누락 수정 및 조회 갯수 100개로 상향 조정)
