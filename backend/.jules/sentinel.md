## 2024-05-18 - 🛡️ Sentinel: Enhance AES key derivation with HKDF and fallback
**Vulnerability:** Weak key derivation function (raw SHA-256) used for AES encryption could compromise keys if the `APP_SECRET` was sub-optimal in length or entropy distribution.
**Learning:** Fixing key derivation is a breaking change for existing encrypted stored items (like DB credentials). You must always implement a legacy key derivation fallback loop when upgrading encryption/KDF to avoid rendering existing user data irretrievable.
**Prevention:** Use standardized KDFs (like HKDF, PBKDF2) for derivations rather than direct hash algorithms from the start.
