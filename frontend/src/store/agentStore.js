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
    // slack:   { connected: false, lastTestStatus: null, lastTestAt: null },
    email:   { connected: false, lastTestStatus: null, lastTestAt: null },
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
        let result
        if (channel === 'discord') {
          result = await agentAPI.connectDiscord()
        // } else if (channel === 'slack') {
        //   result = await agentAPI.connectSlack()
        } else {
          result = await agentAPI.connectChannel(channel)
        }

        if (result?.ok || result?.connected) {
          set((state) => {
            const updatedNotifications = {
              ...state.agent.notifications,
              [channel]: {
                connected: true,
                lastTestStatus: result.lastTestStatus || null,
                lastTestAt: result.lastTestAt || null,
              },
            }
            const hasNotification =
              updatedNotifications.discord?.connected ||
              // updatedNotifications.slack?.connected ||
              updatedNotifications.email?.connected
            return {
              agent: {
                ...state.agent,
                notifications: updatedNotifications,
                // 알림 채널 연결 시 에이전트가 설정된 상태면 자동으로 활성화
                isActive: state.agent.isConfigured && hasNotification
                  ? true
                  : state.agent.isActive,
              },
            }
          })
        }
        return result
      },

      getDiscordChannels: async () => {
        return await agentAPI.getDiscordChannels()
      },
      // 5/22일 #slack 추가 (Slack 채널 목록 조회)
      // getSlackChannels: async () => {
      //   return await agentAPI.getSlackChannels() // #slack 추가 (Slack 채널 목록 조회)
      // },

      selectDiscordChannel: async ({ guildId, channelId }) => {
        return await agentAPI.selectDiscordChannel({ guildId, channelId })
      },
      // 5/22일 #slack 추가 (Slack 채널 선택)
      // selectSlackChannel: async ({ workspaceId, channelId }) => {
      //   return await agentAPI.selectSlackChannel({ workspaceId, channelId }) // #slack 추가 (Slack 채널 저장)
      // },

      disconnectNotification: async (channel) => {
        const result = await agentAPI.disconnectChannel(channel)
        if (result?.ok) {
          set((state) => {
            const updatedNotifications = {
              ...state.agent.notifications,
              [channel]: {
                connected: false,
                lastTestStatus: null,
                lastTestAt: null,
              },
            }
            const hasNotification =
              updatedNotifications.discord?.connected ||
              // updatedNotifications.slack?.connected ||
              updatedNotifications.email?.connected
            return {
              agent: {
                ...state.agent,
                notifications: updatedNotifications,
                // 마지막 알림 채널 해제 시 자동 일시정지
                isActive: hasNotification ? state.agent.isActive : false,
              },
            }
          })
        }
        return result
      },

      testNotification: async (channel) => {
        let result
        if (channel === 'discord') {
          result = await agentAPI.testDiscord()
        // } else if (channel === 'slack') {
        //   result = await agentAPI.testSlack()
        } else {
          result = await agentAPI.testChannel(channel)
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
                  lastTestStatus: 'fail',
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
        if (result.ok) {
          set({
            agent: {
              ...initialAgent,
              keywords: result.keywords || [],
              sources: result.sources || [],
              language: result.language || 'ko',
              summaryLength: result.summary_length || 'medium',
              collectCount: result.collect_count || 5,
              frequency: result.frequency || 'daily',
              isConfigured: !!result.is_configured,
              isActive: !!result.is_active,
              notifications: {
                discord: result.notifications?.discord || initialAgent.notifications.discord,
                // slack: result.notifications?.slack || initialAgent.notifications.slack,
                email: result.notifications?.email || initialAgent.notifications.email,
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
      // localStorage 구버전 데이터와 새 initialAgent 구조를 안전하게 병합
      merge: (persisted, current) => ({
        ...current,
        agent: {
          ...current.agent,
          ...persisted.agent,
          notifications: {
            ...current.agent.notifications,
            ...persisted.agent?.notifications,
            discord: {
              ...current.agent.notifications.discord,
              ...persisted.agent?.notifications?.discord,
            },
            // slack: {
            //   ...current.agent.notifications.slack,
            //   ...persisted.agent?.notifications?.slack,
            // },
            email: {
              ...current.agent.notifications.email,
              ...persisted.agent?.notifications?.email,
            },
          },
        },
      }),
    },
  ),
)
