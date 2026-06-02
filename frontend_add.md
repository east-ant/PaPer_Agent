# Frontend 변경(추가) — 파일별 정리 (디스코드 ↔ 슬랙)

아래는 파일별로 정리한 변경 목록입니다. 각 파일명 아래에 "무엇 추가/변경"과 해당 함수(설명 + 전체 본문)를 배치했습니다.

---

파일: `src/api/agent.js`
- 무엇이 있는가: OAuth 팝업 연결, 연결 상태 조회, 채널 목록 조회, 채널 선택 저장, 테스트 발송 관련 API 헬퍼들(디스코드와 동일한 역할의 슬랙 함수 추가)

- `connectDiscord()` (기존)
```javascript
export async function connectDiscord() {
  try {
    const urlResult = await apiCall('/api/discord/oauth-url')
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
      'DiscordOAuth',
      `width=${width},height=${height},left=${left},top=${top}`
    )

    if (!popup) {
      return { ok: false, message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.' }
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
        if (event?.data?.type !== 'discord-oauth-complete') return
        if (!event.data.ok) {
          finish({ ok: false, message: event.data.message || 'Discord 연결 실패' })
          return
        }
        setTimeout(() => { apiCall('/api/discord/status').then(finish) }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) {
          setTimeout(() => { apiCall('/api/discord/status').then(finish) }, 500)
        }
      }, 500)

      const waitTimeout = setTimeout(() => { try { popup.close() } catch {} ; finish({ ok: false, message: 'Discord 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' }) }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return { ok: false, error: error.message, message: 'Discord 연동 실패' }
  }
}
```

- `connectSlack()` (신규)
```javascript
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
      return { ok: false, message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.' }
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
        if (event?.data?.type !== 'slack-oauth-complete') return
        if (!event.data.ok) { finish({ ok: false, message: event.data.message || 'Slack 연결 실패' }); return }
        setTimeout(() => { apiCall('/api/slack/status').then(finish) }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) { setTimeout(() => { apiCall('/api/slack/status').then(finish) }, 500) }
      }, 500)

      const waitTimeout = setTimeout(() => { try { popup.close() } catch {} ; finish({ ok: false, message: 'Slack 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' }) }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return { ok: false, error: error.message, message: 'Slack 연동 실패' }
  }
}
```

**설명:**
- 이유: Discord만 지원하던 OAuth/알림 기능을 Slack 워크스페이스/채널로 확장하기 위해 추가했습니다.
- 역할: 백엔드에서 받은 Slack OAuth URL로 팝업을 열고, 팝업의 완료 신호(`slack-oauth-complete`)를 받아 서버 상태를 재조회해 연결 결과를 반영합니다. 팝업 닫힘과 타임아웃을 처리합니다.

- 상태 조회
```javascript
export async function getDiscordStatus() { return apiCall('/api/discord/status') }
export async function getSlackStatus()   { return apiCall('/api/slack/status') }
```

**설명:**
- 이유: 프론트에서 Slack 연결 상태를 표시하거나 분기 처리를 하기 위해 서버의 연결 상태를 조회할 필요가 있습니다.
- 역할: `/api/slack/status`를 호출해 Slack 연결 여부 및 관련 메타 정보를 반환합니다.
```
```

- 채널 목록 조회
```javascript
export async function getDiscordChannels() { return apiCall('/api/discord/channels') }
export async function getSlackChannels()   { return apiCall('/api/slack/channels') }
```

**설명:**
- 이유: 사용자가 Slack 워크스페이스 내에서 알림을 받을 채널을 선택할 수 있도록 UI에 채널 목록을 제공해야 합니다.
- 역할: 서버에서 Slack 워크스페이스와 채널 목록을 받아 UI에 표시 가능한 형태로 반환합니다.
```
```

- 테스트 알림
```javascript
export async function testDiscord() { return apiCall('/api/notice/test/discord', { method: 'POST' }) }
export async function testSlack()   { return apiCall('/api/notice/test/slack', { method: 'POST' }) }
```

**설명:**
- 이유: 사용자가 설정한 Slack 채널로 알림이 정상적으로 전송되는지 확인하기 위한 테스트 전송 기능이 필요합니다.
- 역할: 서버의 테스트 알림 엔드포인트를 호출해 선택된 Slack 채널로 테스트 메시지를 전송하고, 성공/실패 결과를 UI에 반영합니다.
```
```

- 알림 대상 채널 선택 저장
```javascript
export async function selectDiscordChannel({ guildId, channelId }) {
  return apiCall('/api/discord/channel', {
    method: 'PATCH',
    body: JSON.stringify({ guild_id: guildId, channel_id: channelId }),
  })
}

export async function selectSlackChannel({ workspaceId, channelId }) {
  return apiCall('/api/slack/channel', {
    method: 'PATCH',
    body: JSON.stringify({ workspace_id: workspaceId, channel_id: channelId }),
  })
}

**설명:**
- 이유: UI에서 사용자가 선택한 Slack 워크스페이스와 채널을 서버에 저장해 이후 알림 발송 대상로 사용하기 위해 추가했습니다.
- 역할: `workspaceId`와 `channelId`를 서버에 PATCH 요청으로 저장하여, 해당 채널을 알림 대상로 설정합니다.
```

---

파일: `src/store/agentStore.js`
- 무엇이 있는가: UI에서 호출하는 store 래퍼들 및 디스코드 분기와 슬랙 분기 추가

- 변경/추가된 핵심 (요약 및 코드 스니펫)
```javascript
// connectNotification: discord 분기
if (channel === 'discord') {
  const result = await agentAPI.connectDiscord()
  if (result && result.ok) {
    set((state) => ({
      agent: {
        ...state.agent,
        notifications: {
          ...state.agent.notifications,
          discord: { connected: true, lastTestStatus: result.lastTestStatus || null, lastTestAt: result.lastTestAt || null },
        },
      },
    }))
  }
}

// connectNotification: slack 분기 (추가)
if (channel === 'slack') {
  const result = await agentAPI.connectSlack()
  if (result && result.ok) {
    set((state) => ({
      agent: {
        ...state.agent,
        notifications: {
          ...state.agent.notifications,
          slack: { connected: true, lastTestStatus: result.lastTestStatus || null, lastTestAt: result.lastTestAt || null },
        },
      },
    }))
  }
  return result
}

// store wrapper: 채널 목록 / 채널 선택 / 테스트
getSlackChannels: async () => { return await agentAPI.getSlackChannels() },
selectSlackChannel: async ({ workspaceId, channelId }) => { return await agentAPI.selectSlackChannel({ workspaceId, channelId }) },
testNotification: if (channel === 'slack') result = await agentAPI.testSlack()
```

---

파일: `src/components/stepper/AgentStepper.jsx`
- 무엇이 있는가: 알림 설정 UI에 Slack 관련 상태와 핸들러 추가

- 추가된 상태 및 핸들러(요약)
```javascript
// 상태
const [slackChannels, setSlackChannels] = useState([])
const [selectedSlackChannel, setSelectedSlackChannel] = useState('')
const [selectedSlackWorkspaceId, setSelectedSlackWorkspaceId] = useState('')

// useEffect: step 4에서 Slack 연결 시 채널 로드
if (agent.notifications?.slack?.connected) { const result = await getSlackChannels(); setSlackChannels(result.channels) }

// 핸들러
async function handleSlackChannelChange(id) { setSelectedSlackChannel(String(id)); await selectSlackChannel({ workspaceId: selectedSlackWorkspaceId, channelId: id }) }
async function handleConnect(channel) { if (channel === 'slack') await connectNotification('slack') }
async function handleTest(channel) { if (channel === 'slack') await testNotification('slack') }
```

---

필요하면 각 파일의 정확한 라인 링크로 바꿔드리거나, 더 많은 함수(예: UI 내부의 세부 핸들러 전체 본문)도 같은 방식으로 포함해 드립니다.

---

기능: OAuth 팝업 연결

기존 디스코드:
```javascript
export async function connectDiscord() {
  try {
    const urlResult = await apiCall('/api/discord/oauth-url')
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
      'DiscordOAuth',
      `width=${width},height=${height},left=${left},top=${top}`
    )

    if (!popup) {
      return { ok: false, message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.' }
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
        if (event?.data?.type !== 'discord-oauth-complete') return
        if (!event.data.ok) {
          finish({ ok: false, message: event.data.message || 'Discord 연결 실패' })
          return
        }
        setTimeout(() => { apiCall('/api/discord/status').then(finish) }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) {
          setTimeout(() => { apiCall('/api/discord/status').then(finish) }, 500)
        }
      }, 500)

      const waitTimeout = setTimeout(() => { try { popup.close() } catch {} ; finish({ ok: false, message: 'Discord 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' }) }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return { ok: false, error: error.message, message: 'Discord 연동 실패' }
  }
}
```

추가한 슬랙 코드:
```javascript
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
      return { ok: false, message: '팝업이 차단되었습니다. 브라우저 팝업 허용 후 다시 시도해주세요.' }
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
        if (event?.data?.type !== 'slack-oauth-complete') return
        if (!event.data.ok) { finish({ ok: false, message: event.data.message || 'Slack 연결 실패' }); return }
        setTimeout(() => { apiCall('/api/slack/status').then(finish) }, 300)
      }

      window.addEventListener('message', handleMessage)

      const checkWindow = setInterval(() => {
        if (popup && popup.closed) { setTimeout(() => { apiCall('/api/slack/status').then(finish) }, 500) }
      }, 500)

      const waitTimeout = setTimeout(() => { try { popup.close() } catch {} ; finish({ ok: false, message: 'Slack 연결 대기 시간이 초과되었습니다. 다시 시도해주세요.' }) }, OAUTH_WAIT_TIMEOUT_MS)
    })
  } catch (error) {
    return { ok: false, error: error.message, message: 'Slack 연동 실패' }
  }
}
```

---

기능: 연결 상태 조회

기존 디스코드:
```javascript
export async function getDiscordStatus() { return apiCall('/api/discord/status') }
```

추가한 슬랙 코드:
```javascript
export async function getSlackStatus() { return apiCall('/api/slack/status') }
```

---

기능: 채널 목록 조회

기존 디스코드:
```javascript
export async function getDiscordChannels() { return apiCall('/api/discord/channels') }
```

추가한 슬랙 코드:
```javascript
export async function getSlackChannels() { return apiCall('/api/slack/channels') }
```

---

기능: 테스트 알림 전송

기존 디스코드:
```javascript
export async function testDiscord() { return apiCall('/api/notice/test/discord', { method: 'POST' }) }
```

추가한 슬랙 코드:
```javascript
export async function testSlack() { return apiCall('/api/notice/test/slack', { method: 'POST' }) }
```

---

기능: 알림 대상 채널 선택 저장 (버튼 → 저장 호출)

기존 디스코드:
```javascript
/**
 * Discord 테스트/알림 대상 채널 선택 저장
 */
export async function selectDiscordChannel({ guildId, channelId }) {
  return apiCall('/api/discord/channel', {
    method: 'PATCH',
    body: JSON.stringify({ guild_id: guildId, channel_id: channelId }),
  })
}
```

추가한 슬랙 코드:
```javascript
/**
 * Slack 테스트/알림 대상 채널 선택 저장 5/22
 */
export async function selectSlackChannel({ workspaceId, channelId }) {
  return apiCall('/api/slack/channel', {
    method: 'PATCH',
    body: JSON.stringify({ workspace_id: workspaceId, channel_id: channelId }),
  })
}
```

---

간단 변경 요약:
- 파일: `src/api/agent.js` — 위의 Slack 함수들 추가
- 파일: `src/store/agentStore.js` — `connectNotification('slack')`, `getSlackChannels`, `selectSlackChannel`, `testNotification('slack')` 등 store 래퍼 추가
- 파일: `src/components/stepper/AgentStepper.jsx` — Slack 관련 상태(`slackChannels`, `selectedSlackChannel`, `selectedSlackWorkspaceId`)와 핸들러(`handleConnect('slack')`, `handleTest('slack')`, `handleSlackChannelChange`) 추가

원하시면 이 파일을 커밋하거나(`git add`/`commit`) 다른 형식으로 출력해 드리겠습니다.
