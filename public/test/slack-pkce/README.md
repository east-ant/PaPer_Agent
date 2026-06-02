# Slack PKCE Local Test

이 폴더는 기존 프론트 코드를 건드리지 않고 Slack OAuth + PKCE를 로컬에서 점검하기 위한 임시 테스트용입니다.

## 실행 방법

1. 프론트 개발 서버를 실행합니다.
   - `npm run dev`
2. 브라우저에서 아래 주소를 엽니다.
   - `http://localhost:5173/test/slack-pkce/index.html`
3. 페이지에서 `PKCE 생성`을 누른 뒤 `OAuth URL 열기`를 누릅니다.
4. Slack 앱 설정의 Redirect URL에는 아래 주소를 등록합니다.
   - `http://localhost:5173/test/slack-pkce/index.html`

## 확인 포인트

- `code_verifier`와 `code_challenge`가 생성되는지
- Slack 로그인 후 이 페이지로 다시 돌아오는지
- URL에 `code`와 `state`가 붙는지

## 주의

- 이 테스트 페이지는 토큰 교환까지 자동 처리하지 않습니다.
- 실제 backend callback 교환까지 하려면 서버 쪽 PKCE 처리도 추가해야 합니다.
