# 최근 구현 및 시스템 수정 내역

## 이메일 로그인 및 OTP 인증 연동

* 이메일 기반 로그인/회원가입 기능 구현
* OTP 인증 메일 발송 기능 연동
* 인증번호 검증 및 만료 처리 구현
* 로그인 실패/인증 실패 예외 처리 추가
* 프론트엔드 로그인 상태 연동

### 추가 수정

* 이메일 로그인 시 Google 계정 정보가 덮어씌워지는 문제 수정
* 이메일 JWT / Google JWT 구분 처리
* Google 프로필 및 연동 상태 유지되도록 DB 로직 수정

---

# 이메일 논문 알림 시스템 연동

* 논문 수집 후 이메일 자동 발송 기능 구현
* HTML 이메일 템플릿 적용
* 논문 링크 및 요약 내용 포함
* 이메일 발송 실패 예외 처리 추가
* 발송 기록 DB 저장 로직 수정

---

# 이메일 북마크 기능 구현

이메일에서 바로 논문을 북마크할 수 있도록 기능 구현

## 구현 방식

* 이메일 내부 북마크 버튼 클릭 시:

```text id="9j6xtq"
/bookmark?id=...&title=...&link=...
```

형태로 프론트엔드 페이지 이동

* Query Parameter 기반으로 북마크 자동 저장 처리
* 저장 완료 후 메인 페이지 이동

---

# 대시보드 DB 연동 구조 수정

기존 사용자 기준 통계를 전체 서비스 기준 통계로 변경

## 수정 내용

* papers 테이블 전체 데이터를 기준으로 통계 집계
* user_email 필터 제거

## 적용 항목

* 오늘 총 수집 논문 수
* 최근 신규 논문 수
* 논문 트렌드
* 인기 키워드 통계

---

# Discord 및 DB 저장 문제 수정

## 수정 내용

* Discord Webhook 연동 수정
* 논문 발송 기록 저장 수정
* scheduled_alerts 저장 로직 수정
* sent_papers 저장 안정화
* notification_settings 중복 생성 방지

---

# DB 저장 오류 및 스키마 문제 수정

## bookmarks 저장 오류 수정

### 문제

```text id="3cxxl5"
Field 'user_id' doesn't have a default value
```

### 수정

```sql id="7n3oqh"
user_id = user_email
```

명시적으로 저장 처리

---

## bookmarks 조회 오류 수정

### 문제

```text id="7pqx4s"
Unknown column 'created_at'
```

### 수정

```sql id="7hl7bz"
bookmarked_at AS created_at
```

별칭 처리 적용

---

# scheduled_alerts 스키마 수정

## 수정 내용

* alert_type 컬럼 추가
* status ENUM 확장

```sql id="vksk69"
ENUM('success', 'failed', 'sent', 'pending')
```

---

# Discord 인터랙션 저장 문제 수정

## 문제

두 번째 논문부터 저장 실패 발생

## 수정

```text id="q9ub4e"
save:<index>:<user_email>
```

형태로 사용자 식별 정보 추가

---

# 대시보드 렌더링 데이터 보강

## 추가 데이터

* daysAgo
* publishedAt
* journal
* url
* citations

## 결과

* 실시간 렌더링 정상화
* 기간 필터 정상 동작
* 논문 카드 데이터 개선

---

# DB 연결 지연 원인 분석

## 원인

* 요청마다 DB 연결 생성 및 종료
* Railway 원격 MySQL 네트워크 지연

## 향후 개선 예정

* SQLAlchemy Connection Pool 적용
* FastAPI Depends 기반 DB 세션 관리 구조 리팩토링

---

# 최종 결과

* 이메일 OTP 로그인 연동 완료
* 이메일 인증 시스템 구현
* 이메일 논문 알림 자동화
* 이메일 북마크 기능 구현
* Discord 알림 복구
* 대시보드 전역 통계 처리
* DB 저장 안정화
* 논문 발송 기록 관리 개선
* 로그인 세션 충돌 해결
