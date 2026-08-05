# Changelog

## Unreleased
- [BE] 💾 **저장된 ERD View 갱신 API**: editor 권한 사용자가 기존 `diagram_view_uuid`를 유지한 채 이름과 레이아웃을 안전하게 교체할 수 있는 `PUT /api/diagram-views/{diagram_view_uuid}`를 추가했습니다. 정확히 512 KiB인 compact JSON 레이아웃은 허용하고 1바이트 초과는 변경 전 거부하며, 존재 여부 비노출 404와 생성 시각·안정 ID 보존을 유지합니다.
- [BE] 🛡️ **API 요청 본문 사전 제한**: unsafe `/api` 요청을 라우팅·인증·Pydantic 역직렬화 전에 최대 2 MiB(환경변수 `API_REQUEST_BODY_MAX_BYTES`)로 제한합니다. `Content-Length`와 chunked body를 모두 검사하고 OWASP API4:2023 및 ASGI 구현 근거를 doctoring에 기록했습니다.
- [FE] 💾 **데모 저장 View 계약 정합화**: 같은 밀리초에도 고유한 View ID를 생성하고, 이름 1–200자·직렬화 레이아웃 512 KiB 제한을 저장 전 적용하며, 실패한 변경은 store를 보존하고 갱신된 View를 최신순 선두로 이동합니다.
- [BE] 🔒 **공유 export 전 경로 redaction**: 공개 share의 SQL / index-design / reversing-spec export에서 코멘트·`example_value`를 제거합니다. 단위 테스트로 누출을 차단합니다.
- [BE] 🛠️ **함수 인덱스 중복 오탐 수정**: `lower(email)` 등 expression index를 평문 컬럼 인덱스의 중복으로 잘못 판단하지 않도록 괄호 파서를 강화했습니다.
- [Docs] README를 상용 기준 기능 설명으로 갱신 (MVP skeleton 표현 제거, share redaction·diff/export 반영).
- [BE] 🔒 **백엔드 공급망 잠금파일 재생성 (CVE 제거 + 드리프트 정합화)**: `backend/requirements.lock`·`backend/requirements-dev.lock`을 `pyproject.toml`에 맞춰 재컴파일했습니다. `pyasn1` 0.6.3→0.6.4 (PYSEC-2026-3455/3456/3457), `pydantic-settings` 2.12.0→2.14.2 (GHSA-4xgf-cpjx-pc3j, `pyproject.toml`이 이미 `>=2.14.2` 선언)을 제거하고, 잠금파일이 누락하고 있던 직접 의존성(`pyjwt`·`aiohttp`·`requests`·`python-multipart` 등)을 정합화했습니다. `pip-audit`: 수정 버전이 없는 `ecdsa` PYSEC-2026-1325(사이드채널, 업스트림이 범위 외로 명시)만 잔존. hash-locked 재설치 계약 유지.
- [FE] 🪄 **관계 자동 추론 기능 추가**: 컬럼 이름(e.g. `user_id`)을 분석하여 연관된 테이블에 자동으로 Foreign Key Edge를 연결하는 버튼을 ERD 편집기 툴바에 추가했습니다.
- [FE] 🗑️ **모든 노드 지우기 기능 추가**: 캔버스의 모든 테이블 노드와 관계를 한 번에 초기화하는 버튼을 툴바에 추가했습니다.
- [FE] 📋 **테이블 복제 기능 추가**: 편집 모달 내에서 기존 테이블의 구조(컬럼 정보 포함)를 그대로 복사하여 새 테이블 노드로 생성하는 '복제' 버튼을 추가했습니다.
- [FE] `autoInfer.ts`에 대한 단위 테스트 및 UI 컴포넌트 단위 테스트를 추가하여 100% 테스트 커버리지를 유지합니다.
- [FE] ⬇️ **DBML Export**: ERD 다이어그램을 DBML (Database Markup Language) 형식으로 내보낼 수 있는 기능을 추가했습니다. 상단의 DBML 버튼을 클릭하여 다운로드할 수 있습니다.
- [FE] 📚 **Data Dictionary Export**: ERD 테이블/컬럼 메타데이터를 CSV 및 Markdown으로 내보내며, CSV formula injection과 Markdown 렌더링 escape를 적용했습니다.