## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-08-14 - [Prevent XSS in SVG exports]
**Vulnerability:** Cross-Site Scripting (XSS) via unvalidated node position data in `exportDiagramSvg`.
**Learning:** SVG attributes built with template literals using user-controlled `x` and `y` coordinates can be exploited to inject arbitrary HTML attributes (like `onload`) if the values are strings instead of numbers.
**Prevention:** Explicitly cast positional values to numbers (e.g., using `Number()`) before using them in calculations or embedding them in SVG strings.
