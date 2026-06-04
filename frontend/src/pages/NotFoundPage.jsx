import { Link } from 'react-router-dom'
import styles from './NotFoundPage.module.css'

export default function NotFoundPage() {
  return (
    <main className={`flex min-h-screen flex-col items-center justify-center px-6 ${styles.bg}`}>
      <div className="animate-fade-up text-center">
        <p className={`mb-2 text-8xl font-semibold tabular-nums ${styles.code}`}
           style={{ letterSpacing: '-0.04em' }}>
          404
        </p>
        <p className={`mb-1 text-xl font-normal ${styles.title}`}>
          페이지를 찾을 수 없습니다
        </p>
        <p className={`mb-8 text-sm ${styles.desc}`}>
          주소가 잘못되었거나 삭제된 페이지입니다.
        </p>
        <Link
          to="/dashboard"
          className={`inline-flex items-center rounded-xl px-5 py-2.5 text-sm font-medium transition-opacity hover:opacity-85 ${styles.btn}`}
        >
          대시보드로 돌아가기
        </Link>
      </div>
    </main>
  )
}
