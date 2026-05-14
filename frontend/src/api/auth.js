// ── 인증 API ──────────────────────────────────────────
// 백엔드 연결 시 아래 TODO 주석을 실제 fetch 로 교체합니다.

// 즉시 사용 가능한 사용자 데이터 (UI 초기 렌더용)
// 백엔드 연결 시: /auth/me 응답 구조에 맞게 수정
export const CURRENT_USER = {
  name:     '유저이름',
  email:    '123@gmail.com',
  joinedAt: '2024년 1월',
  provider: 'Google',
}

// 현재 로그인된 사용자 정보 조회
export async function getMe() {
  // TODO: return await fetch('/api/auth/me').then((r) => r.json())
  return CURRENT_USER
}

// 로그아웃
export async function logoutUser() {
  // TODO: await fetch('/api/auth/logout', { method: 'POST' })
}
