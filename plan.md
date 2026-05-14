## Plan: paper_ai_agent_c1 알림/디스코드 통합 (Status: COMPLETED)

paper_Agent의 디스코드 OAuth/테스트 알림/스케줄/DB 패턴을 재사용해 paper_ai_agent_c1에 알림 백엔드 구조를 신설했다. 핵심은 backend를 notice, discord, storage_box로 분리하고, 설정 저장 즉시 1회 발송 + 정기 스케줄 발송을 함께 보장하는 것이다. 사용자 결정사항에 따라 MySQL 사용, 저장/재개 시 즉시 발송, 중복 발송 방지 및 중복 보관 방지 로직이 적용되었다.

**Steps (All COMPLETED)**
1. **Phase 0 스키마/정책 확정**: ✅ 완료. 저장/재개 시 즉시 발송 정책 및 중복 방지 필터링 정책 확정.
2. **Phase 1 백엔드 구조 분리**: ✅ 완료. notice, discord, storage_box 폴더 구조화 및 라우팅 완료.
3. **Phase 1-1 DB 확장**: ✅ 완료. `agent_configs`, `notification_settings`, `scheduled_alerts`, `sent_papers`, `bookmarks` 테이블 구축 및 마이그레이션.
4. **Phase 2 디스코드 연결**: ✅ 완료. OAuth 연동, 채널 조회, 테스트 발송 기능 구현.
5. **Phase 3 알림 저장/발송 플로우**: ✅ 완료. 설정 저장 시 `run_immediate_collection`을 통한 즉시 발송 보장.
6. **Phase 4 자동화 스케줄러**: ✅ 완료. APScheduler를 이용한 매일 오후 2시 자동 수집 및 발송 (중복 제외 및 개수 보정 로직 포함).
7. **Phase 5 상태 제어/삭제**: ✅ 완료. 일시정지(is_active=0), 재개(is_active=1), 삭제(초기화) 기능 연동.
8. **Phase 6 프론트 연동**: ✅ 완료. AgentStepper 및 AgentStatusPage 전체 API 연동 및 상태 동기화 안정화.
9. **Phase 7 통합 검증**: ✅ 완료. 중복 저장 방지, 중복 알림 제외 후 개수 보충, Windows 인코딩 이슈 해결 등 최종 고도화 완료.

**Core Improvements & Bug Fixes**
- **중복 방지 고도화**: 알림 발송 시 이미 보낸 논문은 제외하고, 제외된 만큼 새로운 논문을 더 찾아 사용자가 설정한 수집 개수를 항상 채우도록 개선.
- **보관함 중복 방지**: 동일 논문을 여러 번 북마크 하더라도 DB에는 하나만 유지되도록 중복 체크 로직 적용.
- **UI 안정성**: Zustand 스토어의 상태 병합 로직 개선 및 프론트엔드 전반에 Optional Chaining 적용으로 "흰 화면" 에러 원천 차단.
- **Windows 환경 최적화**: 콘솔 인코딩 에러를 방지하기 위해 백엔드 로그에서 모든 이모지 제거.

**Database Schema (Final)**
- `users`: 사용자 기본 정보
- `agent_configs`: 에이전트 수집 설정 (키워드, 소스, 주기, 활성상태 등)
- `notification_settings`: 디스코드/슬랙 연동 정보 및 토큰
- `scheduled_alerts`: 알림 발송 이력 로그
- `sent_papers`: 중복 발송 방지를 위한 논문별 발송 기록
- `bookmarks`: 사용자 보관함 (논문 데이터 저장)

**Current Status**
- 모든 기능이 정상 작동하며, 2PM 자동화 스케줄러가 활성화되어 있습니다.
- 일시정지 시 스케줄러는 중단되지 않으나 실제 발송 단계에서 필터링되어 동작합니다.
- 삭제 시 설정 정보만 초기화되며 보관함 데이터는 안전하게 보존됩니다.
