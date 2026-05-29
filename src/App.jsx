import { useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom'
import LoginPage        from './pages/LoginPage'
import DashboardPage    from './pages/DashboardPage'
import AgentSetupPage   from './pages/AgentSetupPage'
import AgentStatusPage  from './pages/AgentStatusPage'
import ProfilePage      from './pages/ProfilePage'
import LoadingPage      from './pages/LoadingPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import NotFoundPage     from './pages/NotFoundPage'
import ErrorBoundary    from './components/ErrorBoundary'
import Sidebar          from './components/layout/Sidebar'
import Topbar           from './components/layout/Topbar'
import { isLoggedIn }   from './utils/auth'

function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)

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
        </Route>
        {/* 매칭되지 않는 모든 경로 → 404 */}
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  )
}
