"""The provider-neutral credential contract.

Runtime modules never read environment variables or files directly for
credential material. They construct a :class:`SecretReference` (which carries
only non-secret metadata) and hand it to a :class:`CredentialProvider`, which
returns a :class:`ResolvedSecret`. The resolved value is available only via
:meth:`ResolvedSecret.reveal`; ``repr`` / ``str`` / ``%`` formatting and
logging all redact it, so a secret cannot leak into logs, tracebacks, metrics,
or a serialized settings object by accident.

Every failure is a :class:`SecretResolutionError` -- providers fail closed and
never fall back to an unaudited source.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

#: Placeholder shown wherever a secret value would otherwise be rendered.
REDACTED = "***REDACTED***"


class SecretResolutionError(Exception):
    """A credential could not be resolved from an authorized source.

    Raised for missing, empty, oversized, symlinked, path-escaping,
    non-regular, malformed, revoked, expired, ambiguous, or wrong-purpose
    secret material. The message names the *reference* and the *reason*, never
    the secret value.
    """


@dataclass(frozen=True)
class SecretReference:
    """Non-secret metadata identifying one credential to resolve.

    Attributes:
        name: Provider-scoped identifier (for the mounted-file provider, the
            file name under the base directory). Must be a single path
            segment.
        purpose: What the credential is for (e.g. ``"app_secret"``,
            ``"database_dsn"``). Used for audit attribution and, later,
            wrong-purpose rejection.
        provider: Name of the provider expected to serve it.
        version: Optional explicit version/generation to pin.
        intended_consumer: Optional name of the module that will use it.
    """

    name: str
    purpose: str
    provider: str
    version: str | None = None
    intended_consumer: str | None = None

    def __str__(self) -> str:
        """Render the reference without any secret material."""

        parts = [f"name={self.name}", f"purpose={self.purpose}", f"provider={self.provider}"]
        if self.version is not None:
            parts.append(f"version={self.version}")
        return "SecretReference(" + ", ".join(parts) + ")"


@dataclass(frozen=True)
class ResolvedSecret:
    """A resolved credential whose value is accessible only via ``reveal()``.

    Attributes:
        reference: The :class:`SecretReference` this was resolved from.
        retrieved_at: UTC timestamp of resolution.
        audit_reference: An opaque, non-secret handle a caller can log to
            correlate a use with a retrieval (never the value itself).
    """

    reference: SecretReference
    retrieved_at: dt.datetime
    audit_reference: str
    _value: str = field(repr=False)

    def reveal(self) -> str:
        """Return the secret string. Call this as late as possible and never log it."""

        return self._value

    def __str__(self) -> str:
        """Redacted string form -- safe for logs and error messages."""

        return f"ResolvedSecret({self.reference}, value={REDACTED})"

    def __repr__(self) -> str:
        """Redacted repr -- safe for tracebacks and ``%r`` formatting."""

        return self.__str__()

    def __format__(self, format_spec: str) -> str:
        """Redacted for every format spec so ``f"{secret}"`` cannot leak it."""

        return self.__str__()


@runtime_checkable
class CredentialProvider(Protocol):
    """A source of credential material that fails closed.

    Implementations resolve a :class:`SecretReference` to a
    :class:`ResolvedSecret` or raise :class:`SecretResolutionError`. They must
    not log the value, cache it in a way that outlives revocation without a
    documented TTL, or fall back to an unaudited source.
    """

    @property
    def provider_name(self) -> str:
        """Stable identifier for this provider (matched against ``reference.provider``)."""
        ...

    def resolve(self, reference: SecretReference) -> ResolvedSecret:
        """Resolve ``reference`` or raise :class:`SecretResolutionError`."""
        ...
