// ── 에이전트 API ───────────────────────────────────────
// 백엔드 연결 시 각 함수 내부를 실제 fetch 코드로 교체합니다.
// mock 데이터는 src/api/mock/agent.mock.js 에서 관리합니다.
import {
  saveAgentConfig as mockSaveAgentConfig,
  loadAgentConfig as mockLoadAgentConfig,
  getAgentStatus as mockGetAgentStatus,
  connectChannel as mockConnectChannel,
  connectDiscord as mockConnectDiscord,
  getDiscordStatus as mockGetDiscordStatus,
  getDiscordChannels as mockGetDiscordChannels,
  selectDiscordChannel as mockSelectDiscordChannel,
  testChannel as mockTestChannel,
  testDiscord as mockTestDiscord,
  disconnectChannel as mockDisconnectChannel,
  pauseAgent as mockPauseAgent,
  resumeAgent as mockResumeAgent,
  deleteAgent as mockDeleteAgent,
} from './mock/agent.mock'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://paper-agent-altv.onrender.com'
const OAUTH_WAIT_TIMEOUT_MS = 10 * 60 * 1000

async function apiCall(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })

  const payload = await response.json().catch(() => ({}))
  return {
    ok: response.ok,
    status: response.status,
    ...payload,
  }
}

export async function saveAgentConfig(data) {
  return mockSaveAgentConfig(data)
}

export async function loadAgentConfig() {
  return mockLoadAgentConfig()
}

export async function getAgentStatus() {
  return mockGetAgentStatus()
}

export async function connectChannel(channel) {
  return mockConnectChannel(channel)
}

export async function connectDiscord() {
  return mockConnectDiscord()
}

/**
 * Phase 6: Slack OAuth 연결 5/22
 */
export async function connectSlack() {
  try {
    const urlResult = await apiCall('/api/slack/oauth-url')
    if (!urlResult.ok) {
      return urlResult
    }

    const oauthUrl = urlResult.oauth_url
    const width = 500
    const height = 600
    const left = (window.innerWidth - width) / 2
    const top = (window.innerHeight - height) / 2

    const popup = window.open(
      oauthUrl,
      'SlackOAuth',
      `width=${width},height=${height},left=${left},top=${top}`
    )

    if (!popup) {
      return {
        ok: false,
        message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.',
      }
    }

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
        if (event?.data?.type !== 'slack-oauth-complete') return // #slack 추가 (Slack OAuth 완료 신호만 처리)
        if (!event.data.ok) {
          finish({ ok: false, message: event.data.message || 'Slack 연결 실패' })
          return
        }
        setTimeout(() => {
          apiCall('/api/slack/status').then(finish) // #slack 추가 (연결 완료 후 서버 상태 재조회)
        }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) {
          setTimeout(() => {
            apiCall('/api/slack/status').then(finish) // #slack 추가 (팝업 종료 후 상태 재조회)
          }, 500)
        }
      }, 500)

      const waitTimeout = setTimeout(() => {
        try { popup.close() } catch { }
        finish({ ok: false, message: 'Slack 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' })
      }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return {
      ok: false,
      error: error.message,
      message: 'Slack 연동 실패',
    }
  }
}

/**
 * Phase 6: Discord 연결 상태 조회
 */
export async function getDiscordStatus() {
  return mockGetDiscordStatus()
}

/**
 * Phase 6: Slack 연결 상태 조회 5/22
 */
export async function getSlackStatus() {
  return apiCall('/api/slack/status')
}

/**
 * Discord 선택 가능한 채널 목록 조회
 */
export async function getDiscordChannels() {
  return mockGetDiscordChannels()
}

/**
 * Slack 선택 가능한 채널 목록 조회 5/22
 */
export async function getSlackChannels() {
  return apiCall('/api/slack/channels')
}

/**
 * Discord 테스트/알림 대상 채널 선택 저장
 */
export async function selectDiscordChannel({ guildId, channelId }) {
  return mockSelectDiscordChannel({ guildId, channelId })
}

export async function testChannel(channel) {
  return mockTestChannel(channel)
}

/**
 * Slack 테스트/알림 대상 채널 선택 저장 5/22
 */
export async function selectSlackChannel({ workspaceId, channelId }) {
  return apiCall('/api/slack/channel', {
    method: 'PATCH',
    body: JSON.stringify({ workspace_id: workspaceId, channel_id: channelId }),
  })
}

/**
 * Phase 6: 테스트 알림 전송
 */
export async function testDiscord() {
  return mockTestDiscord()
}

export async function disconnectChannel(channel) {
  return mockDisconnectChannel(channel)

/**
 * Phase 6: Slack 테스트 알림 전송 5/22
 */
export async function testSlack() {
  return apiCall('/api/notice/test/slack', { method: 'POST' })
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

export async function pauseAgent() {
  return mockPauseAgent()
}

export async function resumeAgent() {
  return mockResumeAgent()
}

export async function deleteAgent() {
  return mockDeleteAgent()
}
