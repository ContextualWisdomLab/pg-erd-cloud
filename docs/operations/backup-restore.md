# Backup and Restore Runbook

이 runbook은 `pg-erd-cloud`가 저장하는 앱 메타데이터 PostgreSQL을 대상으로 합니다.
대상 고객 DB의 원본 데이터는 저장하지 않지만, 프로젝트, 멤버십, 암호화된 DSN,
스키마 스냅샷, 공유 링크, job queue 상태는 앱 DB에 저장됩니다.

## Commercial Baseline

- RPO: 최대 24시간 데이터 손실을 허용하는 일일 logical backup을 기본 기준으로 합니다.
- RTO: 단일 인스턴스 장애 시 4시간 내 복구 리허설이 가능한 절차를 유지합니다.
- 보관: 최소 7일 daily, 4주 weekly 보관을 권장합니다.
- 검증: 백업 파일 생성만으로 완료하지 않고, 격리 DB에 restore 후 `/healthz`와 핵심 API
  smoke test를 통과해야 합니다.
- secret: `APP_SECRET` 또는 `APP_SECRET_FILE`은 DB 백업과 분리 보관합니다. 이 값이
  유실되면 저장된 DSN ciphertext를 복호화할 수 없습니다.

## Backup

운영 DB 컨테이너 이름이 compose 기본값인 `erd_postgres`일 때:

```bash
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p backups

docker exec erd_postgres \
  pg_dump \
  --username "${POSTGRES_USER:-erd}" \
  --dbname "${POSTGRES_DB:-erd}" \
  --format custom \
  --no-owner \
  --file "/tmp/pg-erd-cloud-${timestamp}.dump"

docker cp "erd_postgres:/tmp/pg-erd-cloud-${timestamp}.dump" \
  "backups/pg-erd-cloud-${timestamp}.dump"

docker exec erd_postgres rm -f "/tmp/pg-erd-cloud-${timestamp}.dump"
sha256sum "backups/pg-erd-cloud-${timestamp}.dump" \
  > "backups/pg-erd-cloud-${timestamp}.dump.sha256"
```

## Restore Drill

복구 검증은 운영 DB에 직접 수행하지 않습니다. 격리된 PostgreSQL에 restore합니다.

```bash
dump_file="backups/pg-erd-cloud-YYYYMMDDTHHMMSSZ.dump"

docker run --rm --name pg-erd-restore-drill \
  -e POSTGRES_DB=erd_restore \
  -e POSTGRES_USER=erd \
  -e POSTGRES_PASSWORD=restore-test-password \
  -p 127.0.0.1:55432:5432 \
  -d postgres:16-alpine

until docker exec pg-erd-restore-drill \
  pg_isready -U erd -d erd_restore -h 127.0.0.1; do
  sleep 1
done

docker cp "$dump_file" pg-erd-restore-drill:/tmp/restore.dump
docker exec pg-erd-restore-drill \
  pg_restore \
  --username erd \
  --dbname erd_restore \
  --clean \
  --if-exists \
  --no-owner \
  /tmp/restore.dump
```

검증 후 정리:

```bash
docker rm -f pg-erd-restore-drill
```

## Application Smoke Test After Restore

복구 DB를 임시 backend에 연결할 때는 운영 secret과 동일한 `APP_SECRET` 또는
`APP_SECRET_FILE`을 사용해야 DSN 복호화 경로를 검증할 수 있습니다.

최소 확인 항목:

- `/healthz`가 `{"ok": true}`를 반환합니다.
- `alembic current`가 배포 revision과 일치합니다.
- 프로젝트 목록 API가 인증된 사용자에게 정상 응답합니다.
- 기존 공유 링크가 만료 정책과 삭제 API에 맞게 동작합니다.
- 최근 성공 스냅샷의 SQL export가 200 응답을 반환합니다.

## Restore Drill Evidence Manifest

복구 drill 결과는 `docs/operations/restore-drills/restore-drill.example.json` 형식의
JSON manifest로 남깁니다. 실제 유료 파일럿이나 고객 staging drill에서는 example을
복사해 날짜, commit, backup artifact, restore target, smoke test 결과, 증거 링크를
실제 값으로 바꿉니다.

필수 evidence:

- backup artifact 경로, 64자 SHA-256, 생성 시각
- digest로 고정된 `postgres:16-alpine` restore target
- `APP_SECRET` 원문이 아닌 secret store 또는 file URI
- `alembic current`와 기대 revision 일치
- `/healthz`, 프로젝트 목록, 공유 링크 조회/폐기 또는 만료, SQL export,
  support bundle redaction smoke 결과
- backup, restore, application smoke 소요 시간

Support bundle redaction smoke는 복구 DB와 동일한 배포 증거에서
`scripts/operations/generate_support_bundle.py`를 실행해 확인합니다. 이 smoke는
bundle 생성이 성공하고 결과 JSON에 raw `APP_SECRET`, DB password, DSN, private key,
billing secret, raw provider metadata, 공개 share URL/token이 남지 않는지를 확인한
뒤 `smoke_tests.support_bundle_redaction=true`로 기록합니다.

검증:

```bash
python scripts/operations/generate_support_bundle.py \
  --commit-sha "$(git rev-parse HEAD)" \
  --billing-provider-catalog-version "catalog-2026-07-02" \
  --healthz-file evidence/healthz.json \
  --support-account-file evidence/support-account.json \
  --backend-log-file evidence/backend-error.log \
  --output evidence/support-bundle.json
python scripts/ci/validate_restore_drill_manifest.py
```

## Failure Handling

- restore가 실패하면 해당 dump는 폐기하고 직전 백업으로 재시도합니다.
- `APP_SECRET` 유실 또는 불일치로 DSN 복호화가 실패하면 DB restore만으로 완전 복구가
  불가능합니다. secret 보관소에서 올바른 값을 복구하기 전까지 운영 전환을 중단합니다.
- migration mismatch가 있으면 앱을 올리지 말고, 현재 배포 commit의 alembic revision과
  restore DB의 revision을 먼저 맞춥니다.
- migration rollback이 빈번해질 가능성이 높으면 [migration rollback policy](./migration-rollback.md)
  를 함께 점검하고, 장애 징후 발생 시 [incident response runbook](./incident-response.md)을 병행합니다.

## Recurring Review

- 매주 1회 restore drill을 수행하고 결과를 운영 이슈 또는 변경 기록에 남깁니다.
- `compose.prod.yaml`, DB major version, migration 전략, secret 주입 방식이 바뀔 때마다
  이 runbook을 같은 PR에서 갱신합니다.
