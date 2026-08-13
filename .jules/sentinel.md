## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-19 - Replacing Vulnerable python-jose with PyJWT
**Vulnerability:** `python-jose` 라이브러리는 유지보수되지 않으며 `ecdsa`의 취약한 버전에 대한 의존성을 고정하여(PYSEC-2026-1325 유발) 암호화 취약점에 노출되었습니다.
**Learning:** 애플리케이션을 잠재적인 암호화 취약점에 노출시킬 수 있음을 알게 되었습니다.
**Prevention:** 보안 의존성을 보장하고 `python-jose`와 관련된 취약점을 피하기 위해 백엔드에서 JWT 처리에 `PyJWT[crypto]`를 사용합니다.
