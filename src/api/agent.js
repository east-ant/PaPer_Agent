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

export async function getDiscordStatus() {
  return mockGetDiscordStatus()
}

export async function getDiscordChannels() {
  return mockGetDiscordChannels()
}

export async function selectDiscordChannel({ guildId, channelId }) {
  return mockSelectDiscordChannel({ guildId, channelId })
}

export async function testChannel(channel) {
  return mockTestChannel(channel)
}

export async function testDiscord() {
  return mockTestDiscord()
}

export async function disconnectChannel(channel) {
  return mockDisconnectChannel(channel)
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
