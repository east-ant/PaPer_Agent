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
