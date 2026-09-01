"""Local mounted-file credential provider (standalone / Compose deployments).

Reads ``<base_dir>/<name>`` -- the Docker / Podman ``/run/secrets`` pattern --
and fails closed on anything that is not a plain, non-empty, size-bounded
regular file directly inside the base directory. This is the explicit
``local_secret_file`` deployment profile; there is no hidden fallback to
environment variables.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
from pathlib import Path

from app.secret_provider.contract import (
    ResolvedSecret,
    SecretReference,
    SecretResolutionError,
)

#: Default cap on a mounted secret file (64 KiB). Anything larger is rejected.
DEFAULT_MAX_BYTES = 64 * 1024


class LocalMountedFileProvider:
    """Resolve credentials from files mounted under a fixed base directory.

    Args:
        base_dir: Directory the secret files live in (default ``/run/secrets``).
        max_bytes: Reject any secret file larger than this (default 64 KiB).
    """

    provider_name = "local_secret_file"

    def __init__(
        self,
        base_dir: str | os.PathLike[str] = "/run/secrets",
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        """Bind the base directory and the per-file size cap."""

        self._base_dir = Path(base_dir)
        self._max_bytes = int(max_bytes)

    def _reject(self, reference: SecretReference, reason: str) -> SecretResolutionError:
        """Build a fail-closed error that names the reference and reason only."""

        return SecretResolutionError(
            f"{reference} could not be resolved by {self.provider_name}: {reason}"
        )

    def _resolve_path(self, reference: SecretReference) -> Path:
        """Validate ``reference.name`` and return the vetted absolute file path."""

        name = reference.name
        if not name or name in {".", ".."}:
            raise self._reject(reference, "empty or dot secret name")
        if "/" in name or "\\" in name or "\x00" in name:
            raise self._reject(reference, "secret name must be a single path segment")
        if Path(name).is_absolute():
            raise self._reject(reference, "secret name must not be absolute")

        try:
            base = self._base_dir.resolve(strict=True)
        except OSError as exc:
            raise self._reject(reference, f"base directory unavailable: {exc}") from exc

        target = base / name
        if target.is_symlink():
            raise self._reject(reference, "secret file is a symlink")
        try:
            resolved = target.resolve(strict=True)
        except OSError as exc:
            raise self._reject(reference, f"secret file not found: {exc}") from exc
        if resolved.parent != base:
            raise self._reject(reference, "secret file escapes the base directory")
        if not resolved.is_file():
            raise self._reject(reference, "secret path is not a regular file")
        return resolved

    def resolve(self, reference: SecretReference) -> ResolvedSecret:
        """Read and validate the mounted file, or raise ``SecretResolutionError``."""

        if reference.provider not in {self.provider_name, ""}:
            raise self._reject(
                reference, f"reference targets provider {reference.provider!r}"
            )

        path = self._resolve_path(reference)
        size = path.stat().st_size
        if size == 0:
            raise self._reject(reference, "secret file is empty")
        if size > self._max_bytes:
            raise self._reject(
                reference, f"secret file is {size} bytes (> {self._max_bytes})"
            )

        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise self._reject(reference, "secret file is not valid UTF-8") from exc
        if text.endswith("\n"):
            text = text[:-1]
        if not text:
            raise self._reject(reference, "secret file has no content after trimming")

        audit_reference = hashlib.sha256(
            f"{self.provider_name}:{reference.purpose}:{reference.name}:{size}".encode()
        ).hexdigest()[:16]
        return ResolvedSecret(
            reference=reference,
            retrieved_at=dt.datetime.now(dt.timezone.utc),
            audit_reference=audit_reference,
            _value=text,
        )
