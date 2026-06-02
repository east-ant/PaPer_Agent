// ── 논문 API ───────────────────────────────────────────
// 백엔드 연결 시 각 함수 내부를 실제 fetch 코드로 교체합니다.
// mock 데이터는 src/api/mock/papers.mock.js 에서 관리합니다.
import {
  fetchPapers as mockFetchPapers,
  fetchStats as mockFetchStats,
  fetchTrend as mockFetchTrend,
} from './mock/papers.mock'

export async function fetchPapers(options = {}) {
  return mockFetchPapers(options)
}

export async function fetchStats() {
  return mockFetchStats()
}

export async function fetchTrend(period = 'weekly') {
  return mockFetchTrend(period)
}
