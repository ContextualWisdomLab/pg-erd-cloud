# Changelog

## Unreleased
- [BE] 🔥 **Hot-partition·성장 평가 (3차 증분)**: `app.spec.hot_partition_assessment` 분석기와 `GET /api/snapshots/{uuid}/hot-partition-assessment` 읽기 전용 엔드포인트를 추가했습니다. 카탈로그 근거(선언 키·컬럼 타입/기본값·PostgreSQL 파티션 메타데이터)와 선택적 명시 capacity profile만 사용하며 라이브 워크로드를 가정하지 않고 데이터를 표본하지 않습니다. Append-heavy 테이블·무한 보존·단조 증가 키 hot-page·파티션 키가 UNIQUE에 빠진 경우·write/read 편중 축을 근거 등급(`observed`/`declared`/`inferred`/`proposed`)과 함께 탐지하고, capacity profile이 있거나 카탈로그로 선언된 신호일 때만 구체 조치를 `proposed`로 승격합니다. DDL·쓰기 없음. 골든 픽스처 10종 + 리포트/엔드포인트 테스트. EXPLAIN pruning 픽스처는 후속 증분(#947).
- [BE] 🧮 **정규화 평가 리포트·API (2차 증분)**: `GET /api/snapshots/{uuid}/normalization-assessment` 읽기 전용 엔드포인트를 추가했습니다(다른 스냅샷 분석기와 동일한 IDOR-safe 접근 모델, 미조회/미인가 시 uniform not-found). 응답은 버전드 리포트 엔벨로프(`app.spec.normalization_report.build_normalization_report`)로, 스냅샷의 안정적 SHA-256 fingerprint·생성 시각·정규형별/근거 등급별 집계와 한 줄 구매자용 headline을 포함합니다. DDL·쓰기 없음. HTML 표는 후속 증분(#947).
- [BE] 🧮 **정규화·함수종속 평가 (1차 증분)**: 카탈로그 근거만으로 각 기본 relation의 후보키·정규형을 평가하는 `app.spec.normalization_assessment` 분석기를 추가했습니다. 컬럼명 추론 없이 선언된 PK·`UNIQUE`·`NOT NULL`·타입·FK만 사용하며, 모든 finding에 근거 등급(`observed`/`declared`/`inferred`/`proposed`/`waived`)과 오탐 caveat·다음 행동을 부여합니다. 비원자 컬럼(배열·`jsonb`), 후보키 미선언, nullable `UNIQUE` 결정자, 복합키 부분종속 전제조건을 탐지하고 DDL을 생성·실행하지 않습니다. Waiver를 근거 등급으로 기록합니다. 골든 픽스처 14종. 3NF 이행종속·hot-partition·리포트 엔벨로프·HTTP 표면·Rust 경계는 후속 증분(#947). `docs/doctoring/normalization-and-functional-dependency-assessment.md` 참조.
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
