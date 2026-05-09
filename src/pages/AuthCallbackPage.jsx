// 세준이가 추가한것 AuthCallbackPage.jsx 전체
// LoginPage.jsx에 6-9번째줄 추가
// App.jsx에 43-44번째줄 추가

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export default function AuthCallbackPage() {
  const navigate = useNavigate()

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')

    if (token) {
      localStorage.setItem('ppa_token', token)
      localStorage.setItem('ppa_logged_in', 'true')
      window.location.href = '/dashboard'  // navigate 대신 강제 새로고침
    } else {
      navigate('/login', { replace: true })
    }
  }, [])

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <p>로그인 처리 중...</p>
    </div>
  )
}