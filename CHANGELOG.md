# 변경 사항 (CHANGELOG)

## [Unreleased]
### 추가됨
- ERD 다이어그램을 Markdown 환경에서 쉽게 사용할 수 있도록 Mermaid 문법(`erDiagram`)으로 내보내는 기능 추가
- 프론트엔드 UI에 Mermaid 내보내기 버튼 추가

### 수정됨
- Mermaid 내보내기 기능의 XSS 취약점을 방지하기 위해 사용자 입력 데이터(테이블명, 컬럼명 등)를 엄격한 화이트리스트 방식(영숫자 및 밑줄)으로 정제(Sanitization)하도록 개선
