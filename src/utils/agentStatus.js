export function getAgentStatus(agent) {
  if (!agent.isConfigured || agent.keywords.length === 0 || agent.sources.length === 0) return 'unset'

  const hasNotification =
    agent.notifications?.discord?.connected ||
    agent.notifications?.slack?.connected ||
    agent.notifications?.email?.connected

  if (!agent.isActive || !hasNotification) return 'paused'
  return 'active'
}

