import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useBookmarkStore = create(
  persist(
    (set, get) => ({
      bookmarks: [],
      bookmarkedPaperIds: [],
      loading: false,

      fetchBookmarks: async () => {
        const bookmarks = get().bookmarks
        set({
          bookmarkedPaperIds: bookmarks.map((bookmark) => String(bookmark.paper_id)),
          loading: false,
        })
      },

      toggleBookmark: async (paper) => {
        const paperId = String(paper.paper_id ?? paper.arxiv_id ?? paper.id)
        const state = get()
        const isBookmarked = state.bookmarkedPaperIds.includes(paperId)

        if (isBookmarked) {
          if (!window.confirm('보관함에서 이 논문을 삭제하시겠습니까?')) return
          set((current) => ({
            bookmarks: current.bookmarks.filter((bookmark) => String(bookmark.paper_id) !== paperId),
            bookmarkedPaperIds: current.bookmarkedPaperIds.filter((id) => id !== paperId),
          }))
          return
        }

        const bookmark = {
          id: `mock-${paperId}`,
          paper_id: paperId,
          title: paper.title || '제목 없음',
          summary: paper.summary || paper.abstract || '',
          link: paper.link || paper.url || '',
          source: paper.journal || paper.source || 'unknown',
          bookmarked_at: new Date().toISOString(),
        }

        set((current) => ({
          bookmarks: [...current.bookmarks, bookmark],
          bookmarkedPaperIds: [...current.bookmarkedPaperIds, paperId],
        }))
      },

      clearBookmarks: () => set({ bookmarks: [], bookmarkedPaperIds: [] }),
    }),
    {
      name: 'ppa-bookmarks-cache',
      partialize: (state) => ({
        bookmarks: state.bookmarks,
        bookmarkedPaperIds: state.bookmarkedPaperIds,
      }),
    },
  ),
)
