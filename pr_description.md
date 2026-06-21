🧹 [코드 헬스 개선] \`_introspect_snowflake_sync\` 리팩토링

🎯 **무엇을:**
\`backend/app/snowflake_introspect/introspect.py\` 파일에 있는 \`_introspect_snowflake_sync\` 함수에서 스냅샷 데이터를 파싱하고 구조화하는 로직을 추출하여 \`_build_snapshot\`이라는 새로운 헬퍼 함수로 분리했습니다. \`_introspect_snowflake_sync\`는 이제 데이터베이스 연결 및 쿼리 실행의 라이프사이클만 관리하도록 단순화되었습니다.

💡 **왜:**
데이터베이스 연결 라이프사이클(쿼리 실행 및 커넥션 종료 등)과 데이터를 변환하여 최종 결과를 구성하는 로직을 분리함으로써 각 함수의 책임이 명확해졌습니다. 이는 코드의 가독성과 유지보수성을 크게 향상시킵니다.

✅ **검증:**
- 백엔드 테스트 슈트(\`pytest tests/test_snowflake_introspect.py\` 및 전체 테스트)를 실행하여 모든 기능이 기존과 동일하게 정상 동작함을 확인했습니다.
- 추출된 \`_build_snapshot\` 함수가 모든 필수 변수를 올바르게 받고 있음을 코드를 통해 검토했습니다.

✨ **결과:**
Snowflake 데이터 인트로스펙션 코드 내부의 관심사 분리(Separation of Concerns)가 개선되어 더 간결하고 명확한 코드가 되었습니다.
