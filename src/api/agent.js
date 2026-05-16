// ── 에이전트 API ───────────────────────────────────────
// 백엔드 연결: Phase 6 완전 구현

const API_BASE = import.meta.env.VITE_API_URL || 'https://paper-agent-altv.onrender.com'
const API_TIMEOUT_MS = 20000
const OAUTH_WAIT_TIMEOUT_MS = 120000

// 인증 토큰 가져오기
function getAuthToken() {
  return localStorage.getItem('token') || localStorage.getItem('ppa_token')
}

function decodeJwtPayload(token) {
  try {
    const payloadPart = token.split('.')[1]
    if (!payloadPart) return null
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

function getCurrentUserEmail() {
  const storedEmail = localStorage.getItem('user_email')
  if (storedEmail) return storedEmail

  const token = getAuthToken()
  if (!token) return null

  const payload = decodeJwtPayload(token)
  if (payload?.email) {
    localStorage.setItem('user_email', payload.email)
    return payload.email
  }

  return null
}

// API 호출 헬퍼
export async function apiCall(endpoint, options = {}) {
  const token = getAuthToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS)

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
    })

    if (!response.ok && response.status === 401) {
      // 토큰 만료 처리
      localStorage.removeItem('token')
      window.location.href = '/login'
      return null
    }

    return await response.json()
  } catch (error) {
    if (error?.name === 'AbortError') {
      return { ok: false, message: '요청 시간이 초과되었습니다. 다시 시도해주세요.' }
    }
    console.error(`API 호출 실패 [${endpoint}]:`, error)
    return { ok: false, error: error.message }
  } finally {
    clearTimeout(timeoutId)
  }
}

/**
 * Phase 6: 에이전트 설정 저장
 */
export async function saveAgentConfig(data) {
  return apiCall('/api/notice/settings', {
    method: 'POST',
    body: JSON.stringify({
      keywords: data.keywords,
      sources: data.sources,
      language: data.language,
      summary_length: data.summaryLength,
      collect_count: data.collectCount,
      frequency: data.frequency,
    }),
  })
}

/**
 * Phase 6: 에이전트 설정 불러오기 (로그인 후 초기화)
 */
export async function loadAgentConfig() {
  return apiCall('/api/notice/status')
}

/**
 * Phase 6: 에이전트 상태 조회
 */
export async function getAgentStatus() {
  return apiCall('/api/notice/status')
}

/**
 * Phase 6: Discord OAuth 연결
 */
export async function connectDiscord() {
  try {
    // 1. OAuth URL 요청
    const urlResult = await apiCall('/api/discord/oauth-url')
    if (!urlResult.ok) {
      return urlResult
    }

    const oauthUrl = urlResult.oauth_url

    // 2. 팝업 창 열기
    const width = 500
    const height = 600
    const left = (window.innerWidth - width) / 2
    const top = (window.innerHeight - height) / 2

    const popup = window.open(
      oauthUrl,
      'DiscordOAuth',
      `width=${width},height=${height},left=${left},top=${top}`
    )

    if (!popup) {
      return {
        ok: false,
        message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.',
      }
    }

    // 3. 팝업 창에서 콜백 대기
    return new Promise((resolve) => {
      let settled = false
      const finish = (value) => {
        if (settled) return
        settled = true
        window.removeEventListener('message', handleMessage)
        clearInterval(checkWindow)
        clearTimeout(waitTimeout)
        resolve(value)
      }

      const handleMessage = (event) => {
        if (event?.data?.type !== 'discord-oauth-complete') return // # Discord 콜백 완료 신호만 처리
        if (!event.data.ok) {
          finish({ ok: false, message: event.data.message || 'Discord 연결 실패' })
          return
        }
        setTimeout(() => {
          apiCall('/api/discord/status').then(finish) // # 연결 완료 후 서버 상태를 다시 조회
        }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) {
          // 팝업 닫힌 후 상태 재조회
          setTimeout(() => {
            apiCall('/api/discord/status').then(finish)
          }, 500)
        }
      }, 500)

      const waitTimeout = setTimeout(() => {
        try { popup.close() } catch { }
        finish({ ok: false, message: 'Discord 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' })
      }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return {
      ok: false,
      error: error.message,
      message: 'Discord 연동 실패',
    }
  }
}

/**
 * Phase 6: Discord 연결 상태 조회
 */
export async function getDiscordStatus() {
  return apiCall('/api/discord/status')
}

/**
 * Discord 선택 가능한 채널 목록 조회
 */
export async function getDiscordChannels() {
  return apiCall('/api/discord/channels')
}

/**
 * Discord 테스트/알림 대상 채널 선택 저장
 */
export async function selectDiscordChannel({ guildId, channelId }) {
  return apiCall('/api/discord/channel', {
    method: 'PATCH',
    body: JSON.stringify({ guild_id: guildId, channel_id: channelId }),
  })
}

/**
 * Phase 6: 테스트 알림 전송
 */
export async function testDiscord() {
  return apiCall('/api/notice/test/discord', { method: 'POST' })
}

/**
 * Phase 6: 보관함 논문 저장
 */
export async function saveBookmark(paper) {
  return apiCall('/api/storage_box/bookmark', {
    method: 'POST',
    body: JSON.stringify({
      paper_id: paper.id || paper.arxiv_id,
      title: paper.title,
      summary: paper.summary || paper.abstract,
      link: paper.link,
      source: paper.source,
    }),
  })
}

/**
 * Phase 6: 보관함 논문 목록 조회
 */
export async function getBookmarks() {
  return apiCall('/api/storage_box/bookmarks')
}

/**
 * Phase 6: 보관함 논문 삭제
 */
export async function deleteBookmark(bookmarkId) {
  return apiCall(`/api/storage_box/bookmark/${bookmarkId}`, { method: 'DELETE' })
}

/**
 * Phase 4-5: 알림 일시정지
 */
export async function pauseAgent() {
  return apiCall('/api/notice/pause', { method: 'PATCH' })
}

/**
 * Phase 4-5: 알림 재개
 */
export async function resumeAgent() {
  return apiCall('/api/notice/resume', { method: 'PATCH' })
}

/**
 * Phase 5: 에이전트 설정 삭제
 */
export async function deleteAgent() {
  const userEmail = getCurrentUserEmail()
  if (!userEmail) {
    return { ok: false, message: '사용자 정보가 없습니다' }
  }
  return apiCall(`/api/notice/settings/${userEmail}`, { method: 'DELETE' })
}

