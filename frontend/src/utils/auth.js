/** 로그인 상태 확인 */
export function isLoggedIn() {
  return localStorage.getItem('ppa_logged_in') === 'true'
}

/** 로그아웃 처리 (토큰 만료 포함) */
export function clearAuth() {
  localStorage.removeItem('ppa_logged_in')
  localStorage.removeItem('ppa_token')
  localStorage.removeItem('token')
  localStorage.removeItem('user_email')
}

/** Frontend-only mock response. Replace with a fetch wrapper during backend integration. */
export async function authFetch() {
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}
