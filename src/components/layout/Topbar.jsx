import { Link, useSearchParams, useLocation } from 'react-router-dom'
import { useAgentStore } from '../../store/agentStore'
import { getAgentStatus } from '../../utils/agentStatus'
import styles from './Topbar.module.css'

const STATUS = {
  unset:  { label: '미설정',   dot: 'var(--status-neutral-dot)', bg: 'var(--status-neutral-bg)', text: 'var(--status-neutral)' },
  active: { label: '활성화',   dot: 'var(--status-active-dot)',  bg: 'var(--status-active-bg)',  text: 'var(--status-active)' },
  paused: { label: '일시정지', dot: 'var(--status-error-dot)',   bg: 'var(--status-error-bg)',   text: 'var(--status-error)' },
}

const PAGE_TITLES = {
  '/agent':        '에이전트 설정',
  '/agent/status': '에이전트 현황',
  '/profile':      '내 정보',
}

const TABS = [
  { to: '/dashboard',             key: 'total',   label: '통합' },
  { to: '/dashboard?tab=popular', key: 'popular', label: '인기/신규' },
  { to: '/dashboard?tab=archive', key: 'archive', label: '내보관함' },
]

export default function Topbar() {
  const [params]   = useSearchParams()
  const location   = useLocation()
  const { agent }  = useAgentStore()
  const status     = getAgentStatus(agent)
  const tab        = params.get('tab') || 'total'
  const cfg        = STATUS[status]
  const hasDiscord = agent.notifications?.discord?.connected ?? false
  const hasSlack   = agent.notifications?.slack?.connected ?? false
  const hasEmail   = agent.notifications?.email?.connected ?? false
  const isDashboard = location.pathname === '/dashboard'
  const pageTitle   = PAGE_TITLES[location.pathname]

  return (
    <header
      className={`sticky top-0 z-20 flex shrink-0 items-center justify-between backdrop-blur-sm ${styles.topbar}`}
    >
      {isDashboard ? (
        <nav className="flex h-full items-stretch">
          {TABS.map(({ to, key, label }) => (
            <Link
              key={key}
              to={to}
              className={`flex items-center px-4 text-sm font-medium transition-colors duration-150 ${styles.tabLink} ${tab === key ? styles.tabLinkActive : ''}`}
            >
              {label}
            </Link>
          ))}
        </nav>
      ) : (
        <div className="flex h-full items-center px-4">
          <span className={`text-sm font-medium ${styles.pageTitle}`}>{pageTitle}</span>
        </div>
      )}

      {/* 에이전트 상태 pill */}
      <div className="group relative mr-4">
        <button
          className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition-all duration-150"
          style={{ background: cfg.bg, color: cfg.text }}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${status === 'active' ? styles.dotActivePill : ''}`}
            style={status !== 'active' ? { background: cfg.dot } : undefined}
          />
          에이전트 {cfg.label}
        </button>

        <div
          className={`pointer-events-none absolute right-0 top-full mt-2 w-60 rounded-xl p-4 opacity-0 shadow-lg transition-all duration-200 group-hover:pointer-events-auto group-hover:opacity-100 ${styles.popover}`}
        >
          <p className={`mb-1 text-sm font-medium ${styles.popoverTitle}`}>에이전트 {cfg.label}</p>
          {status === 'unset'  && <p className={`text-xs ${styles.statusUnset}`}>아직 설정되지 않았습니다.</p>}
          {status === 'active' && <p className={`text-xs ${styles.statusActive}`}>수집과 알림이 정상 작동 중입니다.</p>}
          {status === 'paused' && <p className={`text-xs ${styles.statusPaused}`}>수집이 중단된 상태입니다.</p>}

          {status !== 'unset' && (
            <div className={`mt-3 space-y-2 pt-3 ${styles.popoverDivider}`}>
              <StatusRow label="Discord" active={hasDiscord} />
              <StatusRow label="Slack"   active={hasSlack} />
              <StatusRow label="이메일"  active={hasEmail} />
            </div>
          )}
          {status === 'active' && (
            <p className={`mt-3 pt-3 text-xs ${styles.popoverDivider} ${styles.popoverMeta}`}>
              다음 수집: 매일 오전 9:00
            </p>
          )}
        </div>
      </div>
    </header>
  )
}

function StatusRow({ label, active }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-xs ${styles.statusRowLabel}`}>{label}</span>
      <span className="flex items-center gap-1.5">
        <span className={`h-2 w-2 rounded-full ${active ? styles.dotConnected : styles.dotDisconnected}`} />
        <span className={`text-xs font-medium ${active ? styles.statusRowConnected : styles.statusRowDisconnected}`}>
          {active ? '연결됨' : '미연결'}
        </span>
      </span>
    </div>
  )
}
