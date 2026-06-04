// Frontend-only mock adapter. Keep this module's exports stable for backend integration.

const MOCK_AGENT_KEY = 'ppa-mock-agent'
const MOCK_DISCORD_CHANNELS = [
  { guild_id: 'ppa-demo', guild_name: 'PPA Demo', channel_id: 'paper-alerts', channel_name: 'paper-alerts' },
  { guild_id: 'ppa-demo', guild_name: 'PPA Demo', channel_id: 'research', channel_name: 'research' },
]

function readAgent() {
  try {
    return JSON.parse(localStorage.getItem(MOCK_AGENT_KEY)) || null
  } catch {
    return null
  }
}

function writeAgent(agent) {
  localStorage.setItem(MOCK_AGENT_KEY, JSON.stringify(agent))
  return agent
}

export async function apiCall() {
  return { ok: true }
}

export async function saveAgentConfig(data) {
  const previous = readAgent() || {}
  writeAgent({
    ...previous,
    keywords: data.keywords,
    sources: data.sources,
    language: data.language,
    summary_length: data.summaryLength,
    collect_count: data.collectCount,
    frequency: data.frequency,
    is_configured: true,
    is_active: previous.is_active ?? true,
    notifications: previous.notifications || {},
  })
  return { ok: true }
}

export async function loadAgentConfig() {
  return { ok: true, ...(readAgent() || {}) }
}

export async function getAgentStatus() {
  return loadAgentConfig()
}

export async function connectChannel(channel) {
  const previous = readAgent() || {}
  const notifications = previous.notifications || {}
  writeAgent({
    ...previous,
    notifications: {
      ...notifications,
      [channel]: {
        ...notifications[channel],
        connected: true,
        lastTestStatus: null,
        lastTestAt: null,
      },
    },
  })
  return { ok: true, channel, connected: true, lastTestStatus: null, lastTestAt: null }
}

export async function connectDiscord() {
  return connectChannel('discord')
}

export async function getDiscordStatus() {
  return { ok: true, connected: true }
}

export async function getDiscordChannels() {
  return {
    ok: true,
    channels: MOCK_DISCORD_CHANNELS,
    discord_channel_ids: readAgent()?.notifications?.discord?.channel_ids || [],
  }
}

export async function selectDiscordChannel({ channelId }) {
  const previous = readAgent() || {}
  const notifications = previous.notifications || {}
  writeAgent({
    ...previous,
    notifications: {
      ...notifications,
      discord: {
        ...notifications.discord,
        connected: true,
        channel_ids: channelId,
      },
    },
  })
  return { ok: true }
}

export async function testChannel(channel) {
  return { ok: true, channel, success: true }
}

export async function testDiscord() {
  return testChannel('discord')
}

export async function disconnectChannel(channel) {
  const previous = readAgent() || {}
  const notifications = previous.notifications || {}
  writeAgent({
    ...previous,
    notifications: {
      ...notifications,
      [channel]: {
        connected: false,
        lastTestStatus: null,
        lastTestAt: null,
      },
    },
  })
  return { ok: true }
}

export async function pauseAgent() {
  writeAgent({ ...(readAgent() || {}), is_active: false })
  return { ok: true }
}

export async function resumeAgent() {
  writeAgent({ ...(readAgent() || {}), is_active: true })
  return { ok: true }
}

export async function deleteAgent() {
  localStorage.removeItem(MOCK_AGENT_KEY)
  return { ok: true }
}
