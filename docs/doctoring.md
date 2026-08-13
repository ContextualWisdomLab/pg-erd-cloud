# Security Patch Guidelines

## References
1. **Unicode Standard 17.0**: Unicode validation against surrogate pairs (`\uD800`-`\uDFFF`) and bounds boundaries (`0x10FFFF`).
2. **OWASP CSV Injection**: Prevention against injection attacks via evaluating arbitrary Excel/Sheets functions prefixed with standard or full-width Unicode characters inside Data Dictionaries.
3. **W3C XML 1.0**: Defense against vector-based scripting escapes in structural SVG attributes.

## Practices
* Hardening React Flow HandleID bounds testing against ReDoS length iterations limits to `10000`.
* Evaluating numeric positions safely via strict cast to prevent nested text execution payloads in DOM SVG outputs.
