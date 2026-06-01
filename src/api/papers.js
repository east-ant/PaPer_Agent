// ── 논문 API ──────────────────────────────────────────
import { mockPapers, mockStats } from '../data/mock'

/**
 * 논문 목록 조회
 * @param {{ limit?: number, sort?: 'latest' | 'trending' }} options
 */
export async function fetchPapers({ limit = 10, sort = 'latest' } = {}) {
  try {
    const result = await apiCall('/papers')
    // /papers는 배열을 직접 반환
    const raw = Array.isArray(result) ? result : (result?.papers ?? [])
    const papers = raw.map(p => ({
      id:          p.id || p.arxiv_id || String(Math.random()),
      arxiv_id:    p.arxiv_id || p.id,
      title:       p.title || '제목 없음',
      authors:     p.authors || '',
      publishedAt: p.published ? String(p.published).slice(0, 10) : (p.year || ''),
      journal:     p.category || p.source || '',
      citations:   p.citations || 0,
      summary:     p.summary || p.abstract || '',
      link:        p.link || '',
      keywords:    [],
      url:         p.link || '',
    }))

    if (sort === 'trending') {
      return papers.sort((a, b) => b.citations - a.citations).slice(0, limit)
    }
    return papers.slice(0, limit)
  } catch {
    return []
  }
}

/** KPI 통계 조회 */
export async function fetchStats() {
  const defaultStats = {
    totalPapers: 0,
    weeklyAdded: 0,
    weeklyGrowth: '0%',
    topKeywords: [],
    updatedAt: '-',
  }
  try {
    const result = await apiCall('/api/notice/stats')
    if (result && result.ok && result.stats) return result.stats
    return defaultStats
  } catch {
    return defaultStats
  }
}

/**
 * 트렌드 차트 데이터 조회
 * @param {'weekly' | 'monthly' | 'yearly'} period
 */
export async function fetchTrend(period = 'weekly') {
  try {
    const result = await apiCall(`/api/notice/stats/trend?period=${period}`)
    if (result && result.ok && result.trend) return result.trend
    return { data: [], labels: [] }
  } catch {
    return { data: [], labels: [] }
  }
}
