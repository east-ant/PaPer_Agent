import { useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import { useAgentStore } from '../store/agentStore'
import styles from './LoginPage.module.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'https://paper-agent-altv.onrender.com'
const IS_LOCAL = API_BASE.includes('localhost') || API_BASE.includes('127.0.0.1')

export default function LoginPage() {
  const [view, setView]       = useState('login')   // 'login' | 'verify'
  const [email, setEmail]     = useState('')
  const [code, setCode]       = useState('')
  const [error, setError]     = useState(null)      // { type: 'wrong'|'expired'|'send_fail', msg, left? }
  const [loading, setLoading] = useState(false)
  const { loadAgent } = useAgentStore()

  // ── 구글 로그인
  function handleGoogleLogin() {
    window.location.href = `${API_BASE}/auth/google`
  }

  // ── 이메일로 인증코드 발송
  async function handleSendCode(e) {
    if (e) e.preventDefault()
    if (!email.trim()) return
    setError(null)
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/auth/email/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      })
      const data = await res.json()
      if (data.ok) {
        setView('verify')
      } else {
        if (data.retryAfterSeconds) {
          setError({ type: 'send_fail', msg: data.message })
        } else {
          setError({ type: 'send_fail', msg: data.message || '이메일 발송에 실패했습니다 잠시 후 다시 시도해주세요' })
        }
      }
    } catch {
      setError({ type: 'send_fail', msg: '이메일 발송에 실패했습니다 잠시 후 다시 시도해주세요' })
    } finally {
      setLoading(false)
    }
  }

  // ── 인증코드 확인
  async function handleVerify(e) {
    e.preventDefault()
    if (!code.trim()) return
    setError(null)
    setLoading(true)
    try {
      if (code.trim().length === 6) {
        const res = await fetch(`${API_BASE}/api/auth/email/verify-code`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: email.trim(), code: code.trim() }),
        })
        const data = await res.json()
        if (data.ok) {
          localStorage.setItem('token', data.token)
          localStorage.setItem('ppa_logged_in', 'true')
          localStorage.setItem('user_email', data.email)
          // 에이전트 설정을 미리 로드한 뒤 대시보드로 이동합니다.
          try { await loadAgent() } catch { /* 실패해도 이동은 합니다 */ }
          window.location.href = '/dashboard'
        } else {
          setError({ type: data.type || 'wrong', msg: data.message || '인증 코드가 올바르지 않습니다' })
        }
      } else {
        setError({ type: 'wrong', msg: '인증 코드 6자리를 입력해주세요' })
      }
    } catch {
      setError({ type: 'send_fail', msg: '오류가 발생했습니다 잠시 후 다시 시도해주세요' })
    } finally {
      setLoading(false)
    }
  }

  // ── 재전송
  async function handleResend() {
    setError(null)
    setCode('')
    handleSendCode()
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-2">

      {/* 백엔드 환경 배지 */}
      <div style={{
        position: 'fixed',
        top: '12px',
        right: '14px',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '5px 10px',
        borderRadius: '99px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.01em',
        backdropFilter: 'blur(8px)',
        border: IS_LOCAL
          ? '1px solid rgba(52,211,153,0.35)'
          : '1px solid rgba(99,102,241,0.35)',
        background: IS_LOCAL
          ? 'rgba(6,78,59,0.75)'
          : 'rgba(30,27,75,0.75)',
        color: IS_LOCAL ? '#6ee7b7' : '#a5b4fc',
        boxShadow: IS_LOCAL
          ? '0 0 12px rgba(52,211,153,0.2)'
          : '0 0 12px rgba(99,102,241,0.2)',
        userSelect: 'none',
      }}>
        <span style={{
          display: 'inline-block',
          width: '7px',
          height: '7px',
          borderRadius: '50%',
          background: IS_LOCAL ? '#34d399' : '#818cf8',
          boxShadow: IS_LOCAL
            ? '0 0 6px #34d399'
            : '0 0 6px #818cf8',
          flexShrink: 0,
        }} />
        <span>{IS_LOCAL ? '🖥 로컬 백엔드' : '☁ 외부 서버'}</span>
        <span style={{ opacity: 0.6, fontSize: '10px', marginLeft: '2px' }}>
          {API_BASE.replace('https://', '').replace('http://', '')}
        </span>
      </div>

      {/* Left — Brand panel */}
      <section className={`relative flex flex-col justify-between overflow-hidden p-10 lg:p-14 ${styles.brandPanel}`}>
        <div className={`pointer-events-none absolute -bottom-32 -left-32 h-80 w-80 rounded-full opacity-20 blur-3xl ${styles.glow}`} />
        <span className="animate-fade-up text-2xl font-semibold tracking-tight text-white" style={{ letterSpacing: '-0.03em' }}>
          PPA
        </span>
        <div>
          <p className="animate-fade-up-1 mb-4 text-4xl font-normal leading-tight text-white lg:text-5xl" style={{ letterSpacing: '-0.03em' }}>
            키워드만 설정하면<br />
            PPA가 매일 논문을<br />
            수집하고 정리합니다.
          </p>
          <p className="animate-fade-up-2 text-sm" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Paper Agent — 논문 자동수집 서비스
          </p>
        </div>
      </section>

      {/* Right — Login / Verify panel */}
      <section className={`flex items-center justify-center px-8 py-16 ${styles.loginPanel}`}>
        <div className="w-full max-w-sm">

          {view === 'login' ? (
            /* ── 로그인 화면 ── */
            <>
              <div className="animate-fade-up mb-10">
                <p className={`mb-2 text-3xl font-normal ${styles.heading}`}>시작하기</p>
                <p className={`text-sm ${styles.subtext}`}>Google 또는 이메일로 로그인하세요</p>
              </div>

              {/* 구글 */}
              <button
                type="button"
                onClick={handleGoogleLogin}
                className={`animate-fade-up-1 group flex w-full items-center justify-center gap-3 rounded-xl border px-5 py-3.5 text-sm font-medium transition-all duration-200 ${styles.googleBtn}`}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                구글 연동하기
              </button>

              {/* 구분선 */}
              <div className={`animate-fade-up-1 my-5 flex items-center gap-3 ${styles.divider}`}>
                <span className={styles.dividerLine} />
                <span className={`text-xs ${styles.dividerText}`}>또는</span>
                <span className={styles.dividerLine} />
              </div>

              {/* 이메일 입력 */}
              <form onSubmit={handleSendCode} className="animate-fade-up-2 space-y-3">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="이메일 주소"
                  required
                  className={`w-full rounded-xl border px-4 py-3 text-sm outline-none transition-colors ${styles.emailInput}`}
                />
                {error?.type === 'send_fail' && (
                  <p className={`text-xs ${styles.errorWarn}`}>⚠ {error.msg}</p>
                )}
                <button
                  type="submit"
                  disabled={loading || !email.trim()}
                  className={`w-full rounded-xl px-5 py-3.5 text-sm font-medium transition-all duration-200 ${styles.submitBtn} ${loading || !email.trim() ? styles.submitBtnDisabled : ''}`}
                >
                  {loading ? '전송 중...' : '로그인하기'}
                </button>
              </form>
            </>
          ) : (
            /* ── 인증코드 화면 ── */
            <>
              <button
                type="button"
                onClick={() => { setView('login'); setCode(''); setError(null) }}
                className={`animate-fade-up mb-8 flex items-center gap-1.5 text-sm transition-colors ${styles.backBtn}`}
              >
                <ArrowLeft size={14} />
                이메일 변경
              </button>

              <div className="animate-fade-up-1 mb-8">
                <p className={`mb-2 text-3xl font-normal ${styles.heading}`}>인증코드 확인</p>
                <p className={`text-sm leading-relaxed ${styles.subtext}`}>
                  <span className={styles.emailHighlight}>{email}</span>으로<br />
                  인증 코드를 보냈습니다.
                </p>
              </div>

              <form onSubmit={handleVerify} className="animate-fade-up-2 space-y-3">
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  placeholder="인증 코드 6자리"
                  maxLength={6}
                  required
                  className={`w-full rounded-xl border px-4 py-3 text-center text-lg tracking-widest outline-none transition-colors ${styles.emailInput} ${error?.type === 'wrong' || error?.type === 'expired' ? styles.emailInputError : ''}`}
                />

                {/* 에러 메시지 */}
                {error?.type === 'wrong' && (
                  <p className={`text-xs ${styles.errorMsg}`}>✕ {error.msg}</p>
                )}
                {error?.type === 'expired' && (
                  <p className={`text-xs ${styles.errorMsg}`}>✕ {error.msg}</p>
                )}
                {error?.type === 'locked' && (
                  <p className={`text-xs ${styles.errorMsg}`}>✕ {error.msg}</p>
                )}
                {error?.type === 'send_fail' && (
                  <p className={`text-xs ${styles.errorWarn}`}>⚠ {error.msg}</p>
                )}

                <button
                  type="submit"
                  disabled={loading || code.length < 6}
                  className={`w-full rounded-xl px-5 py-3.5 text-sm font-medium transition-all duration-200 ${styles.submitBtn} ${loading || code.length < 6 ? styles.submitBtnDisabled : ''}`}
                >
                  {loading ? '확인 중...' : '확인'}
                </button>
              </form>

              <div className="mt-4 flex gap-4">
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={loading}
                  className={`text-xs transition-colors ${styles.linkBtn}`}
                >
                  인증 코드 재전송
                </button>
                <button
                  type="button"
                  onClick={() => { setView('login'); setCode(''); setError(null) }}
                  className={`text-xs transition-colors ${styles.linkBtn}`}
                >
                  이메일 변경
                </button>
              </div>
            </>
          )}

        </div>
      </section>
    </div>
  )
}
