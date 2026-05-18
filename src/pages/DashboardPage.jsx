import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAgentStore } from '../store/agentStore'
import { useBookmarkStore } from '../store/bookmarkStore'
import { getAgentStatus } from '../utils/agentStatus'
import { fetchPapers, fetchStats, fetchTrend } from '../api/papers'
import { ArrowUpRight, ExternalLink, TrendingUp, BookOpen, Bookmark } from 'lucide-react'
import styles from './DashboardPage.module.css'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip as ChartTooltip,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ChartTooltip)

// 백엔드 연결 시: fetchTrend(period) 로 교체
// 주별은 mock.js의 trend/trendLabels와 동기화, 월별/년별은 독립 mock
// TREND_SETS mock은 제거됨

export default function DashboardPage() {
  const [params] = useSearchParams()
  const tab = params.get('tab') || 'total'
  const { agent, loadAgent } = useAgentStore()  // loadAgent 추가
  const { fetchBookmarks } = useBookmarkStore()
  const status = getAgentStatus(agent)

  useEffect(() => {
    loadAgent()        // 추가
    fetchBookmarks()
  }, [])              // fetchBookmarks 의존성 제거

  if (status === 'unset') return <EmptyState />

  return (
    <main className="flex-1 p-4">
      {tab === 'popular' && <PopularPage />}
      {tab === 'archive' && <ArchivePage />}
      {tab !== 'popular' && tab !== 'archive' && <TotalPage agent={agent} />}
    </main>
  )
}

/* ── Empty state ── */
function EmptyState() {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <div className={`animate-fade-up w-full max-w-sm rounded-2xl p-8 text-center ${styles.card}`}>
        <div className={`mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl ${styles.emptyIcon}`}>
          <BookOpen size={20} className={styles.emptyIconSvg} />
        </div>
        <h2 className={`mb-1.5 text-base font-medium ${styles.emptyTitle}`}>아직 수집된 콘텐츠가 없습니다</h2>
        <p className={`mb-6 text-sm leading-relaxed ${styles.emptyDesc}`}>
          에이전트를 설정하면 키워드에 맞는 논문을 자동으로 수집합니다.
        </p>
        <Link to="/agent" className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-85 ${styles.emptyBtn}`}>
          에이전트 설정 <ArrowUpRight size={14} />
        </Link>
      </div>
    </div>
  )
}

/* ── Skeleton ── */
function SkeletonKpi() {
  return (
    <div className={`rounded-xl p-3 ${styles.card}`}>
      <div className="skeleton-shimmer mb-2 h-3 w-16 rounded" />
      <div className="skeleton-shimmer mb-1.5 h-6 w-20 rounded" />
      <div className="skeleton-shimmer h-3 w-28 rounded" />
    </div>
  )
}
function SkeletonSection({ height = 100 }) {
  return (
    <div className={`rounded-xl p-4 ${styles.card}`}>
      <div className="skeleton-shimmer mb-3 h-3.5 w-20 rounded" />
      <div className="skeleton-shimmer rounded-lg" style={{ height }} />
    </div>
  )
}
function SkeletonPaperRow({ first = false }) {
  return (
    <div className={`flex items-start gap-3 px-4 py-3 ${first ? '' : styles.rowDivider}`}>
      <div className="flex-1 space-y-1.5">
        <div className="skeleton-shimmer h-3.5 w-3/4 rounded" />
        <div className="skeleton-shimmer h-3 w-1/2 rounded" />
        <div className="skeleton-shimmer h-3 w-1/3 rounded" />
      </div>
    </div>
  )
}

/* ── Total tab ── */
function TotalPage({ agent }) {
  const [trendPeriod, setTrendPeriod] = useState('주별')
  const [papers, setPapers] = useState([])
  const [stats, setStats] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const defaultStats = { totalPapers: 0, weeklyAdded: 0, weeklyGrowth: '0%', topKeywords: [], updatedAt: '-' }
    Promise.all([
      fetchPapers({ limit: agent.collectCount || 5, sort: 'latest' }).catch(() => []),
      fetchStats().catch(() => defaultStats),
    ]).then(([paperData, statsData]) => {
      if (cancelled) return
      setPapers(Array.isArray(paperData) ? paperData : [])
      setStats(statsData || defaultStats)
      setIsLoading(false)
    }).catch(() => {
      if (cancelled) return
      setStats(defaultStats)
      setIsLoading(false)
    })
    return () => { cancelled = true }
  }, [agent.collectCount])

  if (isLoading) {
    return (
      <div className="animate-fade-up space-y-2">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <SkeletonKpi /><SkeletonKpi /><SkeletonKpi />
        </div>
        <SkeletonSection height={120} />
        <div className={`overflow-hidden rounded-xl ${styles.card}`}>
          <div className={`px-4 py-3 ${styles.cardHeader}`}>
            <div className="skeleton-shimmer h-3.5 w-20 rounded" />
          </div>
          {[...Array(5)].map((_, i) => <SkeletonPaperRow key={i} first={i === 0} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-up space-y-2">
      {/* KPI row */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <KpiCard label="총 수집" value={(stats?.totalPapers ?? 0).toLocaleString()} caption="이번주" captionHighlight={`+${stats?.weeklyAdded ?? 0}`} hero />
        <KpiCard label="이번주 신규" value={stats?.weeklyAdded ?? 0} caption={`지난주 대비 ${stats?.weeklyGrowth ?? '0%'}`} positive />
        <div className={`rounded-xl p-3 ${styles.card}`}>
          <p className={`mb-2 text-xs font-medium ${styles.kpiLabel}`}>
            인기 키워드 TOP3
            <span className={`ml-1.5 ${styles.kpiKeywordMeta}`}>이번 주</span>
          </p>
          <div className="space-y-1.5">
            {(stats?.topKeywords ?? []).length === 0 ? (
              <p className={`text-xs ${styles.kpiRankLabel}`}>수집 데이터가 없습니다</p>
            ) : (stats?.topKeywords ?? []).map((item, i) => (
              <div key={item.label} className="flex items-center justify-between">
                <span className="text-sm">
                  <span className={`mr-1.5 font-medium ${styles.kpiRankNum}`}>{i + 1}</span>
                  <span className={styles.kpiRankLabel}>{item.label}</span>
                </span>
                <span className={`text-xs tabular-nums ${styles.kpiRankCount}`}>{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Trend chart */}
      <section className={`rounded-xl p-5 ${styles.card}`}>
        <div className="mb-5 flex items-start justify-between">
          <div>
            <h2 className={`text-sm font-medium ${styles.trendTitle}`}>수집 트렌드</h2>
            <p className={`mt-0.5 text-xs ${styles.trendMeta}`}>
              {trendPeriod === '주별' ? '최근 12주' : trendPeriod === '월별' ? '최근 12개월' : '연도별'} 논문 수집 추이 · 단위: 편
            </p>
          </div>
          <div className="flex gap-1">
            {['주별', '월별', '년별'].map((l) => (
              <button
                key={l}
                onClick={() => setTrendPeriod(l)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${trendPeriod === l ? styles.trendPeriodActive : styles.trendPeriodInactive}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        <TrendChart period={trendPeriod} />
      </section>

      {/* Latest papers */}
      <section className={`rounded-xl ${styles.card}`}>
        <div className={`flex items-center justify-between px-4 py-3 ${styles.cardHeader}`}>
          <div>
            <h2 className={`text-sm font-medium ${styles.sectionTitle}`}>최신 논문</h2>
            <p className={`text-xs ${styles.sectionMeta}`}>날짜 기준 최신 {agent.collectCount || 5}개</p>
          </div>
          <span className={`text-xs ${styles.updatedAt}`}>{stats?.updatedAt ?? '-'}</span>
        </div>
        <PaperList papers={papers} showSummary summaryLength={agent.summaryLength} />
      </section>
    </div>
  )
}

/* ── Popular tab ── */
function PopularPage() {
  const [newPeriod, setNewPeriod] = useState('7일')
  const [papers, setPapers] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchPapers({ limit: 20, sort: 'latest' }).then((data) => {
      if (cancelled) return
      setPapers(Array.isArray(data) ? data : [])
      setIsLoading(false)
    }).catch(() => {
      if (cancelled) return
      setIsLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  if (isLoading) {
    return (
      <div className="animate-fade-up space-y-2">
        <SkeletonSection height={120} />
        <SkeletonSection height={200} />
      </div>
    )
  }

  const rising = [...papers].sort((a, b) => b.growth - a.growth).slice(0, 3)
  const periodMap = { '1일': 1, '3일': 3, '7일': 7 }
  const filteredNew = papers.filter((p) => p.daysAgo <= periodMap[newPeriod])

  return (
    <div className="animate-fade-up space-y-2">
      {/* 급상승 */}
      <section className={`rounded-xl ${styles.card}`}>
        <div className={`flex items-center gap-2 px-4 py-3 ${styles.cardHeader}`}>
          <TrendingUp size={14} className={styles.trendingIcon} />
          <div>
            <h2 className={`text-sm font-medium ${styles.sectionTitle}`}>이번주 급상승</h2>
            <p className={`text-xs ${styles.sectionMeta}`}>7일 기준 수집 증가율 높은 논문 3개</p>
          </div>
        </div>
        <PaperList papers={rising} />
      </section>

      {/* 신규 수집 */}
      <section className={`rounded-xl ${styles.card}`}>
        <div className={`flex items-center justify-between px-4 py-3 ${styles.cardHeader}`}>
          <div>
            <h2 className={`text-sm font-medium ${styles.sectionTitle}`}>신규 수집</h2>
            <p className={`text-xs ${styles.sectionMeta}`}>최근 {newPeriod} 이내 수집 {filteredNew.length}개</p>
          </div>
          <div className="flex gap-1">
            {['1일', '3일', '7일'].map((l) => (
              <button
                key={l}
                onClick={() => setNewPeriod(l)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${newPeriod === l ? styles.periodBtnActive : styles.periodBtnInactive}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
        {filteredNew.length > 0
          ? <PaperList papers={filteredNew} />
          : <p className={`px-4 py-6 text-center text-sm ${styles.emptyPeriod}`}>해당 기간 내 수집된 논문이 없습니다.</p>
        }
      </section>
    </div>
  )
}

/* ── Archive tab ── */
function ArchivePage() {
  const [sortBy, setSortBy] = useState('최신순')
  const { bookmarks, loading } = useBookmarkStore()
  const { agent } = useAgentStore()

  // DB에서 반환된 bookmarks를 PaperList가 그릴 수 있는 형태로 맵핑
  const mappedBookmarks = bookmarks.map(b => ({
    id: b.id, // DB id for deletion
    paper_id: b.paper_id,
    arxiv_id: b.paper_id,
    title: b.title,
    summary: b.summary,
    url: b.link,
    link: b.link,
    journal: b.source,
    publishedAt: b.bookmarked_at ? b.bookmarked_at.slice(0, 10) : '방금 전',
    authors: '',
    citations: 0,
    keywords: []
  }))

  const sortedPapers = [...mappedBookmarks].sort((a, b) =>
    b.publishedAt.localeCompare(a.publishedAt) // 일단 최신순만
  )

  if (loading) {
    return (
      <div className="animate-fade-up">
        <div className={`overflow-hidden rounded-xl ${styles.card}`}>
          <div className={`flex items-center justify-between px-4 py-3 ${styles.cardHeader}`}>
            <div className="skeleton-shimmer h-3.5 w-20 rounded" />
            <div className="skeleton-shimmer h-6 w-24 rounded-lg" />
          </div>
          {[...Array(5)].map((_, i) => <SkeletonPaperRow key={i} first={i === 0} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="animate-fade-up">
      <section className={`overflow-hidden rounded-xl ${styles.card}`}>
        <div className={`flex items-center justify-between px-4 py-3 ${styles.cardHeader}`}>
          <div>
            <h2 className={`text-sm font-medium ${styles.archiveTitle}`}>내 보관함</h2>
            <p className={`text-xs ${styles.archiveMeta}`}>저장된 논문 {sortedPapers.length}개</p>
          </div>
          {sortedPapers.length > 0 && (
            <div className="flex gap-1">
              {['최신순', '인용순'].map((l) => (
                <button
                  key={l}
                  onClick={() => setSortBy(l)}
                  className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${sortBy === l ? styles.periodBtnActive : styles.periodBtnInactive}`}
                >
                  {l}
                </button>
              ))}
            </div>
          )}
        </div>

        {sortedPapers.length === 0 ? (
          <div className="flex flex-col items-center justify-center px-4 py-14 text-center">
            <div className={`mb-3 flex h-10 w-10 items-center justify-center rounded-xl ${styles.archiveEmptyIcon}`}>
              <Bookmark size={18} className={styles.archiveEmptyIconSvg} />
            </div>
            <p className={`text-sm font-medium ${styles.archiveEmptyTitle}`}>아직 저장된 논문이 없어요</p>
            <p className={`mt-1 text-xs leading-relaxed ${styles.archiveEmptyDesc}`}>
              논문 목록에서 북마크 아이콘을 눌러<br />보관함에 추가해보세요.
            </p>
          </div>
        ) : (
          <PaperList papers={sortedPapers} showSummary summaryLength={agent.summaryLength} />
        )}
      </section>
    </div>
  )
}

/* ── Sub-components ── */
function KpiCard({ label, value, caption, captionHighlight, positive, hero }) {
  return (
    <div className={`rounded-xl p-3 ${hero ? styles.kpiHeroCard : styles.card}`}>
      <p className={`mb-2 text-xs ${styles.kpiLabel}`}>{label}</p>
      <p
        className={`tabular-nums font-medium ${positive ? styles.kpiValuePositive : styles.kpiValueDefault}`}
        style={{
          fontSize: hero ? 'clamp(28px, 3vw, 32px)' : 'clamp(18px, 2vw, 22px)',
          letterSpacing: '-0.03em',
          lineHeight: 1.0,
        }}
      >
        {value}
      </p>
      <p className={`mt-1.5 text-xs ${styles.kpiCaption}`}>
        {caption}
        {captionHighlight && (
          <span className={`ml-1 font-medium ${styles.kpiCaptionHighlight}`}>{captionHighlight}</span>
        )}
      </p>
    </div>
  )
}

function TrendChart({ period }) {
  const [chartDataState, setChartDataState] = useState({ data: [], labels: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const p = period === '주별' ? 'weekly' : period === '월별' ? 'monthly' : 'yearly'
    fetchTrend(p).then(res => {
      if (cancelled) return
      setChartDataState(res)
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [period])

  const { data, labels } = chartDataState

  if (loading) return <div className="flex h-[240px] items-center justify-center text-xs text-gray-400">데이터 로드 중...</div>
  if (!data || data.length === 0) return <div className="flex h-[240px] items-center justify-center text-xs text-gray-400">데이터가 없습니다</div>

  const dataMax = Math.max(...data)
  const yMax = Math.ceil((dataMax + 10) / 25) * 25
  const stepSize = yMax <= 100 ? 25 : yMax <= 400 ? 100 : 250

  const chartData = {
    labels,
    datasets: [{
      data,
      borderColor: '#5B5BD6',
      borderWidth: 2.5,
      tension: 0,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: '#5B5BD6',
      pointBorderWidth: 0,
      pointHoverBackgroundColor: '#5B5BD6',
    }],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#111111',
        titleColor: 'rgba(255,255,255,0.55)',
        bodyColor: '#ffffff',
        titleFont: { size: 11, family: 'Pretendard' },
        bodyFont: { size: 13, weight: '600', family: 'Pretendard' },
        padding: { x: 12, y: 10 },
        cornerRadius: 6,
        displayColors: false,
        callbacks: {
          title: (items) => items[0].label,
          label: (item) => `수집 논문  ${item.parsed.y}편`,
        },
      },
    },
    scales: {
      x: {
        offset: true,
        grid: { display: false },
        border: { display: false },
        ticks: { color: '#6B7280', font: { size: 11, family: 'Pretendard' }, maxTicksLimit: 7, maxRotation: 0 },
      },
      y: {
        min: 0,
        max: yMax,
        grid: { color: 'rgba(0,0,0,0.05)', drawTicks: false },
        border: { display: false },
        ticks: { color: '#6B7280', font: { size: 11, family: 'Pretendard' }, stepSize, padding: 10, callback: (v) => `${v}` },
      },
    },
  }

  return (
    <div className={`rounded-lg ${styles.chartBg}`} style={{ height: '240px', padding: '12px 8px 8px 0' }}>
      <Line data={chartData} options={options} />
    </div>
  )
}

const SUMMARY_FIELD = { short: 'summaryShort', medium: 'summary', full: 'summaryFull' }

function PaperList({ papers, showSummary = false, summaryLength = 'medium' }) {
  const { toggleBookmark, bookmarkedPaperIds } = useBookmarkStore()
  const field = SUMMARY_FIELD[summaryLength] ?? 'summary'

  return (
    <div>
      {papers.map((paper, i) => {
        // falsy 체크 시 빈 문자열도 유효할 수 있으므로 ?? 사용, 혹은 명시적 우선순위
        const paperId = String(paper.paper_id ?? paper.arxiv_id ?? paper.id)
        const isBookmarked = bookmarkedPaperIds.includes(paperId)
        
        return (
          <div
            key={paperId + '-' + i} // 중복 방지
            className={`group relative ${styles.paperRow} ${i > 0 ? styles.rowDivider : ''}`}
          >
            <a href={paper.url || paper.link} target="_blank" rel="noreferrer" className="flex items-start gap-3 px-4 py-3 pr-9">
              <div className="min-w-0 flex-1">
                <h3 className={`mb-0.5 text-sm font-medium leading-snug ${styles.paperTitle}`}>{paper.title}</h3>
                {showSummary && (
                  <p className={`mb-1 line-clamp-2 text-xs leading-relaxed ${styles.paperSummary}`}>{paper[field] || paper.summary}</p>
                )}
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <span className={`text-xs ${styles.paperMeta}`}>
                    {Array.isArray(paper.authors) ? paper.authors.join(', ') : (paper.authors || 'Unknown')} · {paper.publishedAt}
                  </span>
                  {(paper.keywords || []).map((kw) => (
                    <span key={kw} className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles.keyword}`}>{kw}</span>
                  ))}
                </div>
                <p className={`mt-0.5 text-xs ${styles.paperJournal}`}>{paper.journal} · 인용 {paper.citations}</p>
              </div>
              <ExternalLink size={12} className={`mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-40 ${styles.externalIcon}`} />
            </a>

            <button
              type="button"
              onClick={() => toggleBookmark(paper)}
              className={`absolute right-3 top-3 rounded p-0.5 transition-all duration-150 ${isBookmarked ? styles.bookmarkBtnActive : styles.bookmarkBtn
                }`}
              title={isBookmarked ? '보관함에서 제거' : '보관함에 추가'}
            >
              <Bookmark size={13} fill={isBookmarked ? 'var(--accent)' : 'none'} strokeWidth={1.5} />
            </button>
          </div>
        )
      })}
    </div>
  )
}
