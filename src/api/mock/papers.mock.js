// Frontend-only mock adapter. Keep return shapes aligned with the dashboard.
import { mockPapers, mockStats } from '../../data/mock'

const MONTHLY_TREND = {
  data: [45, 88, 120, 95, 140, 185, 210, 178, 240, 290, 265, 340],
  labels: ['7월', '8월', '9월', '10월', '11월', '12월', '1월', '2월', '3월', '4월', '5월', '6월'],
}

const YEARLY_TREND = {
  data: [120, 340, 890, 1248],
  labels: ['2021', '2022', '2023', '2024'],
}

export async function fetchPapers({ limit = 10, sort = 'latest' } = {}) {
  const papers = [...mockPapers]
  if (sort === 'trending') {
    papers.sort((a, b) => b.growth - a.growth)
  }
  return papers.slice(0, limit)
}

export async function fetchStats() {
  return mockStats
}

export async function fetchTrend(period = 'weekly') {
  if (period === 'monthly') return MONTHLY_TREND
  if (period === 'yearly') return YEARLY_TREND
  return { data: mockStats.trend, labels: mockStats.trendLabels }
}
