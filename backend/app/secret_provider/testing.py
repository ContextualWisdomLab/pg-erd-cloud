"""Deterministic in-memory credential provider for tests.

No files, no network, no clock skew -- ``resolve`` returns the same value for
the same name every time and fails closed for an unknown name.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping

from app.secret_provider.contract import (
    ResolvedSecret,
    SecretReference,
    SecretResolutionError,
)

#: Fixed timestamp so resolved secrets compare equal across calls in a test.
_FIXED_RETRIEVED_AT = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


class DeterministicTestProvider:
    """Serve credentials from an in-memory mapping of ``name -> value``.

    Args:
        mapping: The known credentials. Unknown names fail closed.
    """

    provider_name = "deterministic_test"

    def __init__(self, mapping: Mapping[str, str]) -> None:
        """Copy the ``name -> value`` mapping this provider will serve."""

        self._mapping = dict(mapping)

    def resolve(self, reference: SecretReference) -> ResolvedSecret:
        """Return the mapped value or raise ``SecretResolutionError``."""

        if reference.provider not in {self.provider_name, ""}:
            raise SecretResolutionError(
                f"{reference} targets provider {reference.provider!r}, "
                f"not {self.provider_name}"
            )
        try:
            value = self._mapping[reference.name]
        except KeyError as exc:
            raise SecretResolutionError(
                f"{reference} is not known to {self.provider_name}"
            ) from exc
        audit_reference = hashlib.sha256(
            f"{self.provider_name}:{reference.purpose}:{reference.name}".encode()
        ).hexdigest()[:16]
        return ResolvedSecret(
            reference=reference,
            retrieved_at=_FIXED_RETRIEVED_AT,
            audit_reference=audit_reference,
            _value=value,
        )
