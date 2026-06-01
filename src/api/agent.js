// ── 에이전트 API ───────────────────────────────────────

/** 에이전트 설정 저장 */
export async function saveAgentConfig(data) {
  void data
  return { ok: true }
}

/** 에이전트 설정 불러오기 */
export async function loadAgentConfig() {
  return null
}

/** 알림 채널 OAuth 연결 */
export async function connectChannel(channel) {
  void channel
  return { connected: true, lastTestStatus: 'success', lastTestAt: Date.now() }
}

/** 테스트 알림 전송 */
export async function testChannel(channel) {
  void channel
  return { success: true }
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

