// ── 인증 API ──────────────────────────────────────────

export const CURRENT_USER = {
  name:     '유저이름',
  email:    '123@gmail.com',
  joinedAt: '2024년 1월',
  provider: 'Google',
}

/** 현재 로그인된 사용자 정보 조회 */
export async function getMe() {
  return CURRENT_USER
}

/** 로그아웃 */
export async function logoutUser() {}
