# Changelog

## Unreleased
- [FE] 🪄 **관계 자동 추론 기능 추가**: 컬럼 이름(e.g. `user_id`)을 분석하여 연관된 테이블에 자동으로 Foreign Key Edge를 연결하는 버튼을 ERD 편집기 툴바에 추가했습니다.
- [FE] 🗑️ **모든 노드 지우기 기능 추가**: 캔버스의 모든 테이블 노드와 관계를 한 번에 초기화하는 버튼을 툴바에 추가했습니다.
- [FE] 📋 **테이블 복제 기능 추가**: 편집 모달 내에서 기존 테이블의 구조(컬럼 정보 포함)를 그대로 복사하여 새 테이블 노드로 생성하는 '복제' 버튼을 추가했습니다.
- [FE] `autoInfer.ts`에 대한 단위 테스트 및 UI 컴포넌트 단위 테스트를 추가하여 100% 테스트 커버리지를 유지합니다.
- [FE] ⬇️ **DBML Export**: ERD 다이어그램을 DBML (Database Markup Language) 형식으로 내보낼 수 있는 기능을 추가했습니다. 상단의 DBML 버튼을 클릭하여 다운로드할 수 있습니다.
- [FE] 📚 **Data Dictionary Export**: ERD 테이블/컬럼 메타데이터를 CSV 및 Markdown으로 내보내며, CSV formula injection과 Markdown 렌더링 escape를 적용했습니다.
