import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import LoginPage        from './pages/LoginPage'
import DashboardPage    from './pages/DashboardPage'
import AgentSetupPage   from './pages/AgentSetupPage'
import AgentStatusPage  from './pages/AgentStatusPage'
import ProfilePage      from './pages/ProfilePage'
import LoadingPage      from './pages/LoadingPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import BookmarkPage     from './pages/BookmarkPage'
import NotFoundPage     from './pages/NotFoundPage'
import ErrorBoundary    from './components/ErrorBoundary'
import Sidebar          from './components/layout/Sidebar'
import Topbar           from './components/layout/Topbar'
import { isLoggedIn }   from './utils/auth'
import { useAgentStore } from './store/agentStore'

function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { loadAgent } = useAgentStore()

  useEffect(() => {
    // 토큰이 있을 때만 에이전트 설정을 로드합니다.
    const token = localStorage.getItem('token') || localStorage.getItem('ppa_token')
    if (!token) return
    loadAgent().catch((err) => console.warn('에이전트 설정 로드 실패:', err))
  }, [loadAgent])

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--bg-primary)' }}>
      <Sidebar isOpen={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />
      <div
        className="flex min-h-screen flex-1 flex-col transition-[margin] duration-200"
        style={{ marginLeft: sidebarOpen ? 'var(--sidebar-width)' : 'var(--sidebar-width-collapsed)' }}
      >
        <Topbar />
        <div className="flex flex-1 flex-col" style={{ background: 'var(--bg-primary)' }}>
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </div>
      </div>
    </div>
  )
}

function ProtectedRoute() {
  if (!isLoggedIn()) return <Navigate to="/login" replace />
  return <Layout />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallbackPage />} />
        <Route path="/login"         element={<LoginPage />} />
        <Route path="/loading"       element={<LoadingPage />} />
        <Route path="/" element={<ProtectedRoute />}>
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard"    element={<DashboardPage />} />
          <Route path="agent"        element={<AgentSetupPage />} />
          <Route path="agent/status" element={<AgentStatusPage />} />
          <Route path="profile"      element={<ProfilePage />} />
          <Route path="bookmark"     element={<BookmarkPage />} />
        </Route>
        {/* 매칭되지 않는 모든 경로 → 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
