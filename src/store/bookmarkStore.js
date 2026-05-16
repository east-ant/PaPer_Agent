import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { apiCall } from '../api/agent'

export const useBookmarkStore = create(
  persist(
    (set, get) => ({
      bookmarks: [], // DB에서 가져온 전체 북마크 객체 배열
      bookmarkedPaperIds: [], // O(1) 조회를 위한 ID 배열
      loading: false,

      fetchBookmarks: async () => {
        set({ loading: true })
        try {
          const result = await apiCall('/api/storage_box/bookmarks')
          if (result && result.ok) {
            set({
              bookmarks: result.bookmarks,
              bookmarkedPaperIds: result.bookmarks.map((b) => String(b.paper_id))
            })
          }
        } finally {
          set({ loading: false })
        }
      },

      toggleBookmark: async (paper) => {
        const state = get()
        const paperId = String(paper.paper_id ?? paper.arxiv_id ?? paper.id)
        const isBookmarked = state.bookmarkedPaperIds.includes(paperId)

        if (isBookmarked) {
          if (!window.confirm("보관함에서 이 논문을 삭제하시겠습니까?")) return;
          
          // 제거
          const bookmark = state.bookmarks.find((b) => String(b.paper_id) === paperId)
          if (bookmark) {
            // 낙관적 업데이트 (UI 즉시 반영)
            set((s) => ({
              bookmarks: s.bookmarks.filter((b) => b.id !== bookmark.id),
              bookmarkedPaperIds: s.bookmarkedPaperIds.filter((id) => id !== paperId)
            }))
            // 백엔드 삭제
            await apiCall(`/api/storage_box/bookmark/${bookmark.id}`, { method: 'DELETE' })
          }
        } else {
          // 추가
          // 낙관적 업데이트
          set((s) => ({
            bookmarkedPaperIds: [...s.bookmarkedPaperIds, paperId]
          }))
          // 백엔드 저장
          const result = await apiCall('/api/storage_box/bookmark', {
            method: 'POST',
            body: JSON.stringify({
              paper_id: paperId,
              title: paper.title || '제목 없음',
              summary: paper.summary || paper.abstract || '',
              link: paper.link || paper.url || '',
              source: paper.journal || paper.source || 'unknown'
            })
          })

          if (result && result.ok) {
            // DB ID를 얻기 위해 목록 재조회
            get().fetchBookmarks()
          } else {
            // 실패 시 원상복구
            set((s) => ({
              bookmarkedPaperIds: s.bookmarkedPaperIds.filter((id) => id !== paperId)
            }))
          }
        }
      },

      clearBookmarks: () => set({ bookmarks: [], bookmarkedPaperIds: [] }),
    }),
    {
      name: 'ppa-bookmarks-cache',
      partialize: (state) => ({ 
        bookmarks: state.bookmarks, 
        bookmarkedPaperIds: state.bookmarkedPaperIds 
      }),
    }
  )
)
