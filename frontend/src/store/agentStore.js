import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import * as agentAPI from '../api/agent'

const initialAgent = {
  keywords: [],
  sources: [],
  language: 'ko',
  summaryLength: 'medium',
  collectCount: 5,
  notifications: {
    discord: { connected: false, lastTestStatus: null, lastTestAt: null },
    slack: { connected: false, lastTestStatus: null, lastTestAt: null },
  },
  frequency: 'daily',
  isConfigured: false,
  isActive: false,
}

export const useAgentStore = create(
  persist(
    (set) => ({
      agent: initialAgent,

      setAgent: (partial) =>
        set((state) => ({
          agent: {
            ...state.agent,
            ...partial,
            notifications: {
              ...state.agent.notifications,
              ...(partial.notifications || {}),
            },
          },
        })),

      setNotification: (channel, data) =>
        set((state) => ({
          agent: {
            ...state.agent,
            notifications: {
              ...state.agent.notifications,
              [channel]: {
                ...state.agent.notifications[channel],
                ...data,
              },
            },
          },
        })),

      connectNotification: async (channel) => {
        if (channel === 'discord') {
          const result = await agentAPI.connectDiscord()
          if (result.ok || result.connected) {
            set((state) => ({
              agent: {
                ...state.agent,
                notifications: {
                  ...state.agent.notifications,
                  discord: {
                    connected: true,
                    lastTestStatus: result.lastTestStatus || null,
                    lastTestAt: result.lastTestAt || null,
                  },
                },
              },
            }))
          }
          return result
        }
      },

      getDiscordChannels: async () => {
        return await agentAPI.getDiscordChannels()
      },

      selectDiscordChannel: async ({ guildId, channelId }) => {
        return await agentAPI.selectDiscordChannel({ guildId, channelId })
      },

      disconnectNotification: async (channel) => {
        // Phase 5: 에이전트 삭제로 연결 해제
        const result = await agentAPI.deleteAgent()
        if (result.ok) {
          set((state) => ({
            agent: {
              ...state.agent,
              notifications: {
                ...state.agent.notifications,
                [channel]: {
                  connected: false,
                  lastTestStatus: null,
                  lastTestAt: null,
                },
              },
            },
          }))
        }
        return result
      },

      testNotification: async (channel) => {
        let result
        if (channel === 'discord') {
          result = await agentAPI.testDiscord()
        }
        if (result && result.ok) {
          set((state) => ({
            agent: {
              ...state.agent,
              notifications: {
                ...state.agent.notifications,
                [channel]: {
                  ...state.agent.notifications[channel],
                  lastTestStatus: 'success',
                  lastTestAt: Date.now(),
                },
              },
            },
          }))
        } else if (result) {
          set((state) => ({
            agent: {
              ...state.agent,
              notifications: {
                ...state.agent.notifications,
                [channel]: {
                  ...state.agent.notifications[channel],
                  lastTestStatus: 'failed',
                  lastTestAt: Date.now(),
                },
              },
            },
          }))
        }
        return result
      },

      saveAgent: async (agentData) => {
        const result = await agentAPI.saveAgentConfig(agentData)
        if (result.ok) {
          set((state) => ({
            agent: {
              ...state.agent,
              isConfigured: true,
            },
          }))
        }
        return result
      },

      loadAgent: async () => {
        const result = await agentAPI.loadAgentConfig()
        if (result.ok && result.keywords) {
          set({
            agent: {
              ...initialAgent,
              keywords: result.keywords || [],
              sources: result.sources || [],
              language: result.language || 'ko',
              summaryLength: result.summary_length || 'medium',
              collectCount: result.collect_count || 5,
              frequency: result.frequency || 'daily',
              isConfigured: result.is_configured,
              isActive: result.is_active,
              notifications: {
                discord: result.notifications?.discord || initialAgent.notifications.discord,
                slack: result.notifications?.slack || initialAgent.notifications.slack,
              },
            },
          })
        }
        return result
      },

      pauseAgent: async () => {
        const result = await agentAPI.pauseAgent()
        if (result.ok) {
          set((state) => ({
            agent: { ...state.agent, isActive: false }
          }))
        }
        return result
      },

      resumeAgent: async () => {
        const result = await agentAPI.resumeAgent()
        if (result.ok) {
          set((state) => ({
            agent: { ...state.agent, isActive: true }
          }))
        }
        return result
      },

      resetAgent: () => set({ agent: initialAgent }),
    }),
    {
      name: 'ppa-agent-store',
      partialize: (state) => ({ agent: state.agent }),
    },
  ),
)
