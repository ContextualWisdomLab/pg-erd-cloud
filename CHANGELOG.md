# Changelog

## Unreleased

- [Docs] ADR/PRD/TRD/Architecture/UML/ERD, API·Forward Engineering matrix, threat model, test/operations/release strategy, traceability, references, lifecycle vocabulary, and machine-checked documentation links were added as the canonical authority graph.
- [Security] Strix가 확인한 `nanoid<3.3.17` 개발 의존성 경로를 `3.3.17`로 고정하고 전체 lockfile audit을 0건으로 복구했습니다.
- [Security] host-local TLS terminator가 Docker NAT를 거친 뒤 Traefik에 보이는 최소 direct-peer CIDR만 신뢰하고, 백엔드 rate limit·관측 로그가 `client, trusted-peer` 체인의 실제 client hop을 공통 해석하도록 고정했습니다.
- [Security] bearer share SPA 문서는 정적 서버에서도 `Cache-Control: no-store`로 전달해 브라우저·중간 캐시 저장을 금지했습니다.
- [BE] CORS method allowlist를 실제 API의 `PUT`/`DELETE`까지 맞추고 preflight 회귀 테스트를 추가했습니다.
- [CI] 스키마 드리프트 스크립트를 존재하지 않는 세션 쿠키 인증에서 OIDC/API-key Bearer 인증으로 교정하고, 스냅샷 생성은 별도 pipeline 단계임을 명시했습니다.
- [FE] 🎨 **Live Figma alignment**: authoritative screen nodes and Developer Handoff variables now drive the workspace/editor shell, right-side properties inspector, compact toolbar, responsive 767px behavior, modal sizes, Korean copy, and shared light/dark token layer.
- [FE] ♿ **Modal and destructive-action hardening**: normalized dialogs on a shared shell with labelled modal semantics, initial focus, focus containment, Escape/focus return (including nested SVG interaction targets), explicit backdrop behavior, scroll-safe bodies and footers, keyboard-operable group color radios, and single confirmation at the application mutation boundary.
- [FE/BE] 🔗 **Read-only public share route**: share links now resolve to `/share/{id}` and render only successful, path-scoped allowlisted ERD snapshots while keeping `/api/share/{id}` as the backend data endpoint; newly created links receive a configurable expiry, owners can revoke them through the authenticated API, public capability checks remain primary-consistent, and the UI discloses that it has no revoke button yet.
- [FE] 🌗 **Canvas and typography alignment**: editor and shared canvases follow the system color mode, form controls plus React Flow handles, controls, and relationship lines use accessible semantic boundary tokens, the public viewer cannot re-enable editing, status/navigation text meets contrast requirements, and bundled Inter weights plus a Noto Sans KR fallback keep the Korean UI readable on hosts without CJK system fonts.
- [FE] 🔄 **Project-scoped async isolation**: project transitions clear stale data, expose distinct connection/snapshot loading states, preserve each project's in-flight create operation, serialize snapshot polling, and ignore late metadata, clipboard, and mutation completions outside their owning project.
- [Docs] Replaced deleted Figma node `29:143` as current evidence with the live node inventory and an explicit source-precedence/QA record.

- [BE] 🔒 **Cryptography 50+ 보안 경계 갱신**: `pyproject.toml`과 두 hash-locked 요구사항 파일을 동일한 Cryptography 50+ 해석으로 정합화하여 PKCS#7 오류·타이밍 구분으로 인한 CVE-2026-69247 완화를 실제 설치·검증 경로에 반영했습니다.
- [FE] ⚡ **검색 노드 참조 안정화 및 순차 스냅샷 폴링**: 같은 정규화 검색어와 원본 테이블 데이터에는 장식된 `node.data` 참조를 재사용하여 드래그 중 불필요한 하위 렌더링과 할당을 줄입니다. 스냅샷 폴링은 이전 요청이 끝난 뒤에만 다음 요청을 예약하며, 선택 변경·언마운트 후 도착한 오래된 성공 또는 실패 응답을 무시합니다.

- [BE] 🔒 **공유 export 전 경로 redaction**: 공개 share의 SQL / index-design / reversing-spec export에서 코멘트·`example_value`를 제거합니다. 단위 테스트로 누출을 차단합니다.
- [BE] 🔒 **공개 스냅샷 경계 강화**: 공유 목록·상세·모든 export를 성공 상태로 제한하고 공개 DTO에서 원본 스냅샷 오류 진단을 제거합니다.
- [BE] 🔒 **공개 LLM 비용 경계**: bearer 공유 경로에서는 결정적 Markdown과 LLM prompt만 허용하고, 외부 provider를 호출하는 live draft는 인증된 프로젝트 경로에만 유지합니다.
- [BE] 🛠️ **함수 인덱스 중복 오탐 수정**: `lower(email)` 등 expression index를 평문 컬럼 인덱스의 중복으로 잘못 판단하지 않도록 괄호 파서를 강화했습니다.
- [Docs] README를 상용 기준 기능 설명으로 갱신 (MVP skeleton 표현 제거, share redaction·diff/export 반영).
- [BE] 🔒 **백엔드 공급망 잠금파일 재생성 (CVE 제거 + 드리프트 정합화)**: `backend/requirements.lock`·`backend/requirements-dev.lock`을 `pyproject.toml`에 맞춰 재컴파일했습니다. `pyasn1` 0.6.3→0.6.4 (PYSEC-2026-3455/3456/3457), `pydantic-settings` 2.12.0→2.14.2 (GHSA-4xgf-cpjx-pc3j, `pyproject.toml`이 이미 `>=2.14.2` 선언)을 제거하고, 잠금파일이 누락하고 있던 직접 의존성(`pyjwt`·`aiohttp`·`requests`·`python-multipart` 등)을 정합화했습니다. `pip-audit`: 수정 버전이 없는 `ecdsa` PYSEC-2026-1325(사이드채널, 업스트림이 범위 외로 명시)만 잔존. hash-locked 재설치 계약 유지.
- [FE] 🪄 **관계 자동 추론 기능 추가**: 컬럼 이름(e.g. `user_id`)을 분석하여 연관된 테이블에 Foreign Key Edge를 자동 연결하는 기능을 오른쪽 properties inspector에 추가했습니다.
- [FE] 🗑️ **모든 노드 지우기 기능 추가**: 캔버스의 모든 테이블 노드와 관계를 한 번에 초기화하는 기능을 오른쪽 properties inspector에 추가했습니다.
- [FE] 📋 **테이블 복제 기능 추가**: 편집 모달 내에서 기존 테이블의 구조(컬럼 정보 포함)를 그대로 복사하여 새 테이블 노드로 생성하는 '복제' 버튼을 추가했습니다.
- [FE] `autoInfer.ts`와 관련 UI 컴포넌트의 회귀 테스트를 추가했습니다. 현재 CI에는 전체 production coverage 임계값이 없으므로 100% 보장을 주장하지 않습니다.
- [FE] ⬇️ **DBML Export**: ERD 다이어그램을 DBML (Database Markup Language) 형식으로 내보낼 수 있는 기능을 추가했습니다. 현재 UI에서는 공유/내보내기 modal의 “기타 산출물”에서 다운로드합니다.
- [FE] 📚 **Data Dictionary Export**: ERD 테이블/컬럼 메타데이터를 CSV 및 Markdown으로 내보내며, CSV formula injection과 Markdown 렌더링 escape를 적용했습니다.
