import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const initialAgent = {
  keywords: [],
  sources: [],
  language: 'ko',
  summaryLength: 'medium',
  collectCount: 5,
  notifications: {
    discord: { connected: false, lastTestStatus: null, lastTestAt: null },
    slack:   { connected: false, lastTestStatus: null, lastTestAt: null },
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

      connectNotification: (channel) =>
        set((state) => ({
          agent: {
            ...state.agent,
            notifications: {
              ...state.agent.notifications,
              [channel]: {
                connected: true,
                lastTestStatus: null,
                lastTestAt: null,
              },
            },
          },
        })),

      disconnectNotification: (channel) =>
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
        })),

      testNotification: (channel) =>
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
        })),

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
            slack: {
              ...current.agent.notifications.slack,
              ...persisted.agent?.notifications?.slack,
            },
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
