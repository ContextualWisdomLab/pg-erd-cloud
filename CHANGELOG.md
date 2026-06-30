# 변경 사항 (CHANGELOG)

## [Unreleased]

### 추가된 기능 (Added)
- **보안 강화**: Sentinel 보안 검토(Strix) 결과에 따라 DSN 연결 정보를 프론트엔드 상태(state)에 유지하던 것을 제거하고 `<form>`의 `onSubmit` 핸들러에서 직접 값을 추출하여 백엔드로 전달하도록 개선했습니다.
