import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Mail, Calendar, LogOut } from 'lucide-react'
import { useAgentStore }    from '../store/agentStore'
import { useBookmarkStore } from '../store/bookmarkStore'
import styles from './ProfilePage.module.css'

export default function ProfilePage() {
  const navigate           = useNavigate()
  const { resetAgent }     = useAgentStore()
  const { clearBookmarks } = useBookmarkStore()
  const [user, setUser]    = useState(null)

  useEffect(() => {
    const token = localStorage.getItem('ppa_token')
    if (!token) return
    fetch(`https://paper-agent-altv.onrender.com/auth/me?token=${token}`)
      .then(res => res.json())
      .then(data => setUser(data))
  }, [])

  function handleLogout() {
    localStorage.removeItem('ppa_logged_in')
    localStorage.removeItem('ppa_token')
    resetAgent()
    clearBookmarks()
    navigate('/login')
  }

  if (!user) return null

  const rows = [
    { icon: User,     label: '이름',   value: user.name },
    { icon: Mail,     label: '이메일', value: user.email },
    { icon: Calendar, label: '가입일', value: 'Google 계정' },
  ]

  return (
    <main className="flex-1 p-4">
      <div className="animate-fade-up mx-auto max-w-sm space-y-3">

        {/* 프로필 카드 */}
        <div className={`rounded-xl p-5 text-center ${styles.card}`}>
          {user.picture ? (
            <img
              src={user.picture}
              alt="프로필"
              className="mx-auto mb-3 h-14 w-14 rounded-full object-cover"
            />
          ) : (
            <div className={`mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full text-xl font-medium text-white ${styles.avatar}`}>
              {user.name?.charAt(0)}
            </div>
          )}
          <p className={`text-base font-medium ${styles.name}`}>{user.name}</p>
          <p className={`mt-0.5 text-xs ${styles.email}`}>{user.email}</p>
        </div>

        {/* 계정 정보 */}
        <div className={`overflow-hidden rounded-xl ${styles.card}`}>
          <div className={`px-4 py-3 ${styles.sectionHeader}`}>
            <h2 className="text-sm font-medium">계정 정보</h2>
          </div>
          {rows.map(({ icon: Icon, label, value }, i) => (
            <div
              key={label}
              className={`flex items-center gap-3 px-4 py-3 ${i > 0 ? styles.rowDivider : ''}`}
            >
              <Icon size={14} className={`shrink-0 ${styles.rowIcon}`} />
              <span className={`w-16 shrink-0 text-xs font-medium ${styles.rowLabel}`}>{label}</span>
              <span className={`text-sm ${styles.rowValue}`}>{value}</span>
            </div>
          ))}
        </div>

        {/* 연동 정보 */}
        <div className={`rounded-xl px-4 py-3 ${styles.card}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className={`text-sm font-medium ${styles.providerTitle}`}>Google 계정 연동</p>
              <p className={`text-xs ${styles.providerEmail}`}>{user.email}</p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${styles.connectedBadge}`}>연결됨</span>
          </div>
        </div>

        {/* 로그아웃 */}
        <button
          type="button"
          onClick={handleLogout}
          className={`flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-medium transition-colors ${styles.logoutBtn}`}
        >
          <LogOut size={14} />
          로그아웃
        </button>
      </div>
    </main>
  )
}
