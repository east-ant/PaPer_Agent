// 세준이가 추가한것 AuthCallbackPage.jsx 전체
// LoginPage.jsx에 6-9번째줄 추가
// App.jsx에 43-44번째줄 추가

import { useEffect } from 'react'

function decodeJwtPayload(token) {
  try {
    const payloadPart = token.split('.')[1]
    if (!payloadPart) return null
    const base64 = payloadPart.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=')
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

export default function AuthCallbackPage() {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const token = params.get('token')

    if (token) {
      localStorage.setItem('ppa_token', token)
      localStorage.setItem('token', token)
      localStorage.setItem('ppa_logged_in', 'true')
      const payload = decodeJwtPayload(token)
      if (payload?.email) {
        localStorage.setItem('user_email', payload.email)
      }
      window.location.href = '/dashboard'  // navigate 대신 강제 새로고침
    } else {
      window.location.href = '/login'
    }
  }, [])

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
      <p>로그인 처리 중...</p>
    </div>
  )
}