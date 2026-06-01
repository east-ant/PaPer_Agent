import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAgentStore } from '../store/agentStore'
import { getAgentStatus } from '../utils/agentStatus'
import { ArrowRight } from 'lucide-react'
import styles from './AgentStatusPage.module.css'

const SOURCE_LABELS = {
  arxiv:    'arXiv',
  crossref: 'Crossref',
  semantic: 'Semantic Scholar',
  core:     'CORE',
}

const LAST_COLLECTED = '2024.06.10 오전 09:00'

const STATUS_CFG = {
  unset:  { label: '미설정',   text: 'var(--status-neutral)', dot: 'var(--status-neutral-dot)', bg: 'var(--status-neutral-bg)' },
  not_connected: { label: '연결 필요', text: 'var(--status-neutral)', dot: 'var(--status-neutral-dot)', bg: 'var(--status-neutral-bg)' }, // # 알림 미연결 상태를 별도 표시
  active: { label: '활성화',   text: 'var(--status-active)',  dot: 'var(--status-active-dot)',  bg: 'var(--status-active-bg)' },
  paused: { label: '일시정지', text: 'var(--status-error)',   dot: 'var(--status-error-dot)',   bg: 'var(--status-error-bg)' },
}

export default function AgentStatusPage() {
  const { agent, loadAgent, pauseAgent, resumeAgent } = useAgentStore()
  const [toggleLoading, setToggleLoading] = useState(false)
  const [toggleError, setToggleError] = useState('')
  const status = getAgentStatus(agent)
  const cfg = STATUS_CFG[status]

  const hasDiscord = agent.notifications?.discord?.connected ?? false
  const hasSlack   = agent.notifications?.slack?.connected ?? false
  const hasEmail   = agent.notifications?.email?.connected ?? false
  const hasNotification = hasDiscord || hasSlack || hasEmail

  async function handleToggleActive() {
    if (toggleLoading) return
    if (!hasNotification) return

    setToggleError('')
    setToggleLoading(true)
    try {
      const result = agent.isActive ? await pauseAgent() : await resumeAgent()
      if (!result?.ok) {
        setToggleError(result?.message || '상태 변경에 실패했습니다.')
        return
      }

      // 서버 기준 상태로 재동기화
      await loadAgent()
    } catch (error) {
      setToggleError(`상태 변경 중 오류: ${error.message}`)
    } finally {
      setToggleLoading(false)
    }
  }

  const statusDesc =
    status === 'active'
      ? `수집과 알림이 정상 작동 중입니다. 마지막 수집: ${formatLastCollected(agent.updatedAt)}`
      : status === 'not_connected'
        ? '알림 채널이 아직 연결되지 않아 수집이 대기 중입니다.'
      : status === 'paused'
        ? (!hasNotification
            ? '알림 채널이 미연결 상태로 수집이 중단되었습니다.'
            : '에이전트가 비활성화 상태입니다.')
        : null

  const rows = [
    { label: '키워드',    value: agent.keywords?.length > 0 ? agent.keywords.join(', ') : '—' },
    { label: '소스',      value: agent.sources?.length > 0 ? agent.sources.map((id) => SOURCE_LABELS[id] ?? id).join(', ') : '—' },
    { label: '언어',      value: agent.language === 'ko' ? '한국어' : agent.language === 'en' ? '영어' : '전체' },
    { label: '수집 주기', value: agent.frequency === 'daily' ? '매일' : agent.frequency === '3days' ? '3일마다' : '주간' },
    { label: '수집 수',   value: `${agent.collectCount}개` },
    { label: '요약 범위', value: agent.summaryLength === 'short' ? '초록만' : agent.summaryLength === 'full' ? '전체' : '본문' },
  ]

  return (
    <main className="flex-1 p-4">
      <div className="animate-fade-up mx-auto max-w-2xl space-y-3">

        {/* 상태 카드 */}
        <div className={`rounded-xl p-5 ${styles.card}`}>
          <div className="mb-3 flex items-center justify-between">
            <span className={`text-xs ${styles.cardHeaderLabel}`}>현재 상태</span>
            <div className="flex items-center gap-2">
              {status !== 'unset' && status !== 'not_connected' && ( // # 미연결 상태에서는 일시정지/재개 대신 연결 유도만 표시
                <button
                  type="button"
                  onClick={handleToggleActive}
                  disabled={toggleLoading || (status === 'paused' && !hasNotification)}
                  title={status === 'paused' && !hasNotification ? '알림 채널을 먼저 연결해주세요' : undefined}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                    status === 'active' ? styles.toggleBtnPause : styles.toggleBtnResume
                  } ${status === 'paused' && !hasNotification ? styles.toggleBtnDisabled : ''}`}
                >
                  {toggleLoading ? '처리중...' : status === 'active' ? '일시정지' : '재개'}
                </button>
              )}
              <Link
                to="/agent"
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${styles.editBtn}`}
              >
                {status === 'not_connected' ? '연결하기' : '설정 수정'} {/* # 연결 안 된 경우 바로 연결 화면으로 안내 */}
              </Link>
            </div>
          </div>

          <p className="text-2xl font-medium" style={{ letterSpacing: '-0.02em', color: cfg.text, lineHeight: 1.2 }}>
            {cfg.label}
          </p>

          <p className={`mt-1.5 text-xs leading-relaxed ${styles.statusDesc}`}>
            {status === 'unset' ? (
              <>
                아직 에이전트가 설정되지 않았습니다.{' '}
                <Link to="/agent" className={`font-medium underline ${styles.unsetLink}`}>지금 설정하기</Link>
              </>
            ) : statusDesc}
          </p>

          {toggleError && (
            <p className={`mt-2 text-xs ${styles.statusDesc}`}>{toggleError}</p>
          )}

          {/* 일시정지 상태: 해결 경로 CTA */}
          {(status === 'paused' || status === 'not_connected') && ( // # 미연결/일시정지 모두 안내 박스 사용
            <div className={`mt-3 rounded-lg p-3 ${styles.pausedBox}`}>
              <p className={`mb-2 text-xs ${styles.pausedBoxDesc}`}>
                {!hasNotification
                  ? '알림 채널을 연결하면 에이전트가 자동으로 활성화됩니다.'
                  : '에이전트 설정을 수정해 다시 활성화할 수 있습니다.'}
              </p>
              <Link
                to="/agent"
                className={`inline-flex items-center gap-1 text-xs font-medium ${styles.pausedBoxLink}`}
              >
                {status === 'not_connected' ? '연결하러 가기' : '설정 수정하기'} <ArrowRight size={11} strokeWidth={2} /> {/* # 미연결 상태용 CTA */}
              </Link>
            </div>
          )}
        </div>

        {/* 설정 요약 */}
        {status !== 'unset' && (
          <div className={`overflow-hidden rounded-xl ${styles.card}`}>
            <div className={`px-4 py-3 ${styles.sectionHeader}`}>
              <h2 className="text-sm font-medium">설정 요약</h2>
            </div>
            {rows.map(({ label, value }, i) => (
              <div
                key={label}
                className={`flex items-center gap-3 px-4 py-2.5 ${i > 0 ? styles.rowDivider : ''}`}
              >
                <span className={`w-20 shrink-0 text-xs font-medium ${styles.rowLabel}`}>{label}</span>
                <span className={`text-sm ${styles.rowValue}`}>{value}</span>
              </div>
            ))}
          </div>
        )}

        {/* 알림 채널 상태 */}
        {status !== 'unset' && (
          <div className={`overflow-hidden rounded-xl ${styles.card}`}>
            <div className={`px-4 py-3 ${styles.sectionHeader}`}>
              <h2 className="text-sm font-medium">알림 채널</h2>
            </div>
            {[
              { label: 'Discord', active: hasDiscord },
              { label: 'Slack',   active: hasSlack },
              { label: '이메일',  active: hasEmail },
            ].map(({ label, active }, i) => (
              <div
                key={label}
                className={`px-4 py-2.5 ${i > 0 ? styles.rowDivider : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm ${styles.channelName}`}>{label}</span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${active ? styles.dotConnected : styles.dotDisconnected}`} />
                    <span className={`text-xs font-medium ${active ? styles.textConnected : styles.textDisconnected}`}>
                      {active ? '연결됨' : '미연결'}
                    </span>
                  </span>
                </div>
                {label === 'Discord' && active && agent.notifications?.discord?.channel_ids?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {Array.isArray(agent.notifications?.discord?.channel_ids) && agent.notifications.discord.channel_ids.map(id => (
                      <span key={id} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${styles.channelTag}`}>
                        #{id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
