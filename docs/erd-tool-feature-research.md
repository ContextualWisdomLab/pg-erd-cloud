# ERD 툴 기능 연구 — 시장 기능 지도와 pg-erd-cloud 갭 분석

_조사 대상: dbdiagram.io, DrawSQL, SqlDBM, Vertabelo, ChartDB, erwin Data Modeler,
Atlas, Liquibase/Flyway, Dataedo, dbdocs (2025–2026 공개 자료 기준)._

## 1. 시장의 기능 계층 (모든 툴을 관통하는 분류)

### A. 테이블 스테이크 (없으면 ERD 툴이 아님)
| 기능 | 시장 | pg-erd-cloud |
| --- | --- | --- |
| 비주얼 ERD 편집 (드래그·드롭) | 전부 | ✅ (xyflow 편집기) |
| 라이브 DB 리버스 엔지니어링 | 전부 | ✅ PG + Snowflake (SSRF 가드) |
| SQL DDL 내보내기 | 전부 | ✅ PG/Snowflake + Mermaid/PlantUML/SVG, DBML(#427) |
| 공유 / 협업 링크 | 전부 | ✅ share links |
| 멀티 DB 지원 | ChartDB 5종+, SqlDBM은 DW 특화 | ⚠️ 2종 — **MySQL 부재가 최대 갭** |

### B. 개발자 워크플로 (dbdiagram/dbdocs/ChartDB 계열의 승부처)
| 기능 | 시장 | pg-erd-cloud |
| --- | --- | --- |
| **코드-퍼스트 편집 (DBML/DSL)** | dbdiagram의 핵심; dbdocs는 DBML로 문서 호스팅 | ❌ export만(#427), **import/편집 없음** |
| 스키마 버전 히스토리 + diff | ChartDB "every schema change with diffs" | ✅ 스냅샷 diff (name-keyed, oid-무관) — 더 강함 |
| 단일 쿼리 임포트 (마찰 최소화) | ChartDB 시그니처 | ⚠️ 커넥션 등록 필요 (데모 모드로 일부 상쇄) |
| 호스팅된 공개 스키마 문서 | dbdocs 전체 비즈니스 | ⚠️ share link + data dictionary(#469)로 절반 |

### C. 모던 차별화 (2025–26 신규 경쟁축)
| 기능 | 시장 | pg-erd-cloud |
| --- | --- | --- |
| AI 다이어그램/DDL 방언 변환 | ChartDB AI export, SqlDBM AI Copilot, erwin GenAI | ⚠️ LLM 스펙 드래프트는 있음; **방언 변환·모델 생성 없음** |
| 실시간 동시 편집 | SqlDBM/DrawSQL/ChartDB | ❌ |
| 다이어그램 브랜칭/머지 | SqlDBM | ❌ |
| dbt/Confluence 연동 | SqlDBM | ❌ |
| 셀프호스트 옵션 | ChartDB (오픈소스) | ✅ (docker compose) |

### D. 엔터프라이즈 모델링 (erwin/Vertabelo 계열)
| 기능 | 시장 | pg-erd-cloud |
| --- | --- | --- |
| 논리/물리 모델 분리 (+개념 모델) | erwin·Vertabelo 핵심 | ❌ (물리 모델만) |
| Complete Compare (모델↔DB 동기화) | erwin | ✅ 사실상 = 스냅샷 diff + drift 게이트 |
| 네이밍 표준 강제 | erwin/Vertabelo validation | ✅ naming-lint(#473) — **차별화로 보유** |
| 모델 검증 | Vertabelo | ✅ 분석기 10종이 상회 |
| 비즈니스 용어집 (glossary) | Dataedo | ⚠️ 테이블 주석(#467)이 초기 형태 |

### E. Schema-ops / CI-CD (Atlas/Liquibase/Flyway 계열 — 돈이 되는 축)
| 기능 | 시장 | pg-erd-cloud |
| --- | --- | --- |
| 드리프트 감지 + 교정 SQL | **Atlas의 핵심 상품** | ✅ diff + migration.sql + drift 게이트(#483) |
| 마이그레이션 생성 (up/down) | Liquibase/Flyway | ✅ up(#465)/down(#484) + safety(#468) |
| DB 적용 (dry-run) | Atlas | ✅ apply-sql(#464, 보안리뷰 중) |
| 감사 추적 (audit trail) | Liquibase Pro | ❌ (다음 순번) |
| 프로그래매틱 액세스 | 전부 API 제공 | ✅ API keys(#485) |

## 2. 포지셔닝 결론

pg-erd-cloud는 **다이어그램 툴(ChartDB류)과 schema-ops(Atlas류)의 교집합**에 서 있고,
그 교집합(분석기 스위트 + 드리프트 + 안전분류 + PII 스코핑)은 어느 단일 경쟁사도 다
갖고 있지 않다. 반면 다이어그램 툴로서의 폭(멀티 DB·코드퍼스트·실시간 협업)이 좁다.

## 3. 우선순위 권고 (구현 가능성 × 시장 증거)

1. **DBML import → 설계-퍼스트 워크플로** — DB 없이 DBML로 설계 → snapshot-json 변환
   → 기존 forward 파이프라인(DDL/마이그레이션/적용)에 그대로 태움. 순수 파서라 즉시
   구현 가능. dbdiagram 사용자층을 정면으로 흡수.
2. **MySQL 리버스 엔지니어링** — 시장 최대 OSS DB. 커넥터 의존성/테스트 인프라 필요
   (integration 게이트) — 유닛은 모킹으로 선구현 가능.
3. **ORM 코드 생성 (SQLAlchemy/Prisma)** — 경쟁사 대부분 없음. forward engineering을
   앱 코드까지 확장하는 차별화. 순수 로직.
4. **공개 스키마 문서 페이지** — share link + data dictionary 렌더 = dbdocs 대체.
5. **감사 로그** — Liquibase Pro가 유료로 파는 것. (#467/#485 머지 후 마이그레이션 체인.)
6. (중기) AI 방언 변환·실시간 협업·논리 모델 — 인프라/설계 투자 필요, 별도 설계 문서로.

## 출처
- https://erflow.io/en/blog/dbdiagram-alternatives
- https://talkingschema.ai/blog/best-erd-database-design-tools-2026
- https://chartdb.io/ · https://github.com/chartdb/chartdb
- https://www.quest.com/products/erwin-data-modeler
- https://atlasgo.io/
- https://www.holistics.io/blog/top-database-documentation-tools/
- https://dbdocs.io/
- https://www.dbvis.com/thetable/top-database-cicd-and-schema-change-tools-in-2025/
