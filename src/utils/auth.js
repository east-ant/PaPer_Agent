/** 로그인 상태 확인 */
export function isLoggedIn() {
  return localStorage.getItem('ppa_logged_in') === 'true'
}

/** 로그아웃 처리 (토큰 만료 포함) */
export function clearAuth() {
  localStorage.removeItem('ppa_logged_in')
  localStorage.removeItem('ppa_token')
}

/**
 * fetch 래퍼 — 401 응답 시 자동으로 로그아웃 후 로그인 페이지로 이동
 * 백엔드 API 호출 시 fetch 대신 이걸 사용
 */
export async function authFetch(url, options = {}) {
  const token = localStorage.getItem('ppa_token')

  const res = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (res.status === 401) {
    clearAuth()
    window.location.href = '/login'
    return null
  }

  return res
}
