# Changelog

## Unreleased
- [BE] 📦 **릴리스 증거 매니페스트 조립기 (#953 1차 증분)**: `app/release/manifest.py`의 `build_release_manifest(*, source_commit, backend_version, frontend_version, migration_revisions, dependency_lock_digests, included_prs, known_limitations, generated_at) -> dict`를 추가했습니다. 호출자가 이미 수집한 릴리스 사실(commit·버전·Alembic revision·lock 파일 sha256 다이제스트·포함 PR·알려진 한계·생성 시각)을 검증·정규화해 불변·JSON 직렬화 가능한 단일 매니페스트로 만듭니다. git·네트워크·파일시스템 접근 없음. 검증 실패 시 첫 문제 필드명을 담은 `ValueError`. `migration_revisions`/`included_prs`는 정렬·중복 제거, digest는 `^sha256:[0-9a-f]{64}$` 강제. `is_ga_candidate = len(known_limitations) == 0`(한계가 하나라도 있으면 GA 후보 아님 — 정직성 규칙). 테스트 12종. `docs/doctoring/release-manifest.md`에 필드 계약·후속 증분(SBOM·서명 provenance·operability baseline·마이그레이션 리허설) 기록, NIST SP 800-218·SLSA v1.2 인용.
- [BE] 🔒 **Cryptography 50+ 보안 경계 갱신**: `pyproject.toml`과 두 hash-locked 요구사항 파일을 동일한 Cryptography 50+ 해석으로 정합화하여 PKCS#7 오류·타이밍 구분으로 인한 CVE-2026-69247 완화를 실제 설치·검증 경로에 반영했습니다.
- [FE] ⚡ **검색 노드 참조 안정화 및 순차 스냅샷 폴링**: 같은 정규화 검색어와 원본 테이블 데이터에는 장식된 `node.data` 참조를 재사용하여 드래그 중 불필요한 하위 렌더링과 할당을 줄입니다. 스냅샷 폴링은 이전 요청이 끝난 뒤에만 다음 요청을 예약하며, 선택 변경·언마운트 후 도착한 오래된 성공 또는 실패 응답을 무시합니다.
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
