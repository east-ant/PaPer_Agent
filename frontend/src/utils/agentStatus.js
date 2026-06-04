export function getAgentStatus(agent) {
  if (!agent.isConfigured || !agent.keywords || agent.keywords.length === 0 || !agent.sources || agent.sources.length === 0) return 'unset'

  const hasNotification =
    agent.notifications?.discord?.connected ||
    agent.notifications?.slack?.connected ||
    agent.notifications?.email?.connected

  if (!hasNotification) return 'not_connected' // # 알림 미연결은 일시정지와 분리해서 표시
  if (!agent.isActive) return 'paused'
  return 'active'
}

