import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import styles from './LoadingPage.module.css'

const AGENT_STEPS = ['키워드 분석 중', '최신 논문 찾는 중', '요약 준비 중']

export default function LoadingPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const message  = params.get('message')
  const next     = params.get('next') || '/dashboard'
  const isAgent  = params.get('mode') === 'agent'
  const [stepIdx, setStepIdx] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => navigate(next, { replace: true }), 3000)
    return () => clearTimeout(t)
  }, [navigate, next])

  useEffect(() => {
    if (!isAgent) return
    const t = setInterval(() => setStepIdx((i) => (i + 1) % AGENT_STEPS.length), 900)
    return () => clearInterval(t)
  }, [isAgent])

  const displayMessage = isAgent ? AGENT_STEPS[stepIdx] : message

  return (
    <div className={`flex min-h-screen items-center justify-center ${styles.wrap}`}>
      <div className="animate-fade-up text-center">
        <div className="mx-auto mb-8 h-10 w-10">
          <svg className="animate-spin" viewBox="0 0 40 40" fill="none">
            <circle cx="20" cy="20" r="16" stroke="rgba(255,255,255,0.1)" strokeWidth="3" />
            <path d="M20 4 a16 16 0 0 1 16 16" stroke="var(--accent)" strokeWidth="3" strokeLinecap="round" />
          </svg>
        </div>
        <p className={`text-xl font-medium transition-opacity duration-300 ${styles.message}`}>{displayMessage}</p>
        <p className={`mt-2 text-sm ${styles.sub}`}>잠시만 기다려주세요</p>
        {isAgent && (
          <div className="mt-4 flex justify-center gap-1.5">
            {AGENT_STEPS.map((_, i) => (
              <span
                key={i}
                className="h-1 w-1 rounded-full transition-all duration-300"
                style={{ background: i === stepIdx ? 'var(--accent)' : 'rgba(255,255,255,0.2)', width: i === stepIdx ? '16px' : '4px' }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
