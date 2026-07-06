# API Overview — endpoint catalog (incl. pending PRs)

빠른 리뷰/데모용 카탈로그. **상태**: ✅ main · 🔷 open PR (번호). 인증은 세션(OIDC) 기본,
🔷#485 머지 시 `Authorization: Bearer pgerd_…` API 키 병행. 스냅샷 계열은 전부
`_get_authorized_snapshot` 기반 IDOR-safe (uniform not-found).

## Reverse engineering (DB → 모델)
| Endpoint | 설명 | 상태 |
| --- | --- | --- |
| `POST /api/snapshots/by-project/{proj}` | 스냅샷 잡 생성 (PG/Snowflake) | ✅ |
| — MySQL/MariaDB 방언 (`mysql://`) | introspect 디스패치 확장 | 🔷 #488 |
| `GET /api/snapshots/{id}` | 스냅샷 상태+JSON | ✅ |
| `GET .../inferred-relationships` | 미선언 FK 추론 (이름/타입 휴리스틱) | 🔷 #463 |

## Design-first (모델 → DB 없이)
| `POST /api/dbml/convert` | DBML → snapshot JSON (+DDL) | 🔷 #487 |

## Diff / Migration / Ops
| `GET .../diff?against=` | 구조 diff (name-keyed) | 🔷 #465 |
| `GET .../migration.sql?against=&direction=up\|down` | 마이그레이션 SQL + 롤백 | 🔷 #465/#484 |
| `GET .../migration-safety?against=` | 변경 위험 분류 (safe/warning/destructive) | 🔷 #468 |
| `POST /api/connections/{id}/test` | 연결 프로브 (SSRF-guarded) | 🔷 #466 |
| `POST /api/connections/{id}/apply-sql` | ⚠️ DDL 적용 (dry-run 기본; 보안리뷰) | 🔷 #464 |
| `scripts/ci/check_schema_drift.sh` | CI 드리프트 게이트 (exit 0/1/2) | 🔷 #483 |

## Codegen (모델 → 코드)
| `GET .../export.sql?dialect=` | DDL (PG/Snowflake) | ✅ |
| `GET .../orm-models?flavor=sqlalchemy\|prisma\|typeorm` | ORM 모델 | 🔷 #489/#492 |
| `GET .../schema.graphql` | GraphQL SDL | 🔷 #491 |
| `GET .../reversing-spec.md`, `.../index-design.md` | 스펙/인덱스 가이드 (+LLM) | ✅ |

## Analyzers (스키마 인텔리전스)
| `GET .../schema-health` | no-PK / unindexed-FK / orphan | 🔷 #470 |
| `GET .../sensitive-columns` | PII 스코핑 (PCI DSS/GDPR/PIPA 매핑) | 🔷 #471 |
| `GET .../naming-lint` | 예약어/quoting 필요/케이스 일관성 | 🔷 #473 |
| `GET .../fk-cycles` | 순환 FK (Tarjan SCC) | 🔷 #474 |
| `GET .../stats` | 규모/분포 개요 | 🔷 #475 |
| `GET .../wide-tables` | 비정규화(god table) 탐지 | 🔷 #477 |
| `GET .../index-redundancy` | 중복/prefix-shadow 인덱스 | 🔷 #480 |
| `GET .../audit-columns` | created/updated_at 관례 검사 | 🔷 #481 |
| `GET .../constraint-inventory` | CHECK 규칙 + CASCADE 위험 | 🔷 #482 |

## Docs & Collaboration
| `GET .../data-dictionary.md` | 데이터 사전 (주석 병합) | 🔷 #469 |
| `GET /api/share/{link}` + `.../snapshots/{id}` | 공유 링크 (무인증 read) | ✅ |
| `GET .../snapshots/{id}/docs` | 공개 스키마 문서 HTML (CSP, escaped) | 🔷 #490 |
| `/api/diagram-views`, `/api/annotations` | 저장 뷰 · 테이블 주석 | 🔷 #467 |

## Platform
| `/api/api-keys` (POST/GET/DELETE) | 프로그래매틱 액세스 (해시 저장, 1회 노출) | 🔷 #485 |
| `/api/projects`, `/members`, `/me`, auth | 프로젝트/멤버/인증 | ✅ |

_전체 스키마: FastAPI 자동 OpenAPI (`/docs`). 각 PR은 독립(main 기준)이거나 1단
스택(파운데이션 머지 시 자동 리타깃): #468→#465, #469→#467, #484→#465, #485→#467,
#492→#489._
