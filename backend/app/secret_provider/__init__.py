"""Auditable credential-provider boundary (issue #946).

Environment variables and mounted files are *bootstrap transport*; runtime
modules consume secrets through a single provider interface so access can be
attributed, versioned, and rotated. This first increment ships the typed
boundary plus a local mounted-file provider and a deterministic test provider;
``Settings`` is not wired to it yet.
"""

from app.secret_provider.contract import (
    CredentialProvider,
    ResolvedSecret,
    SecretReference,
    SecretResolutionError,
)
from app.secret_provider.local_file import LocalMountedFileProvider
from app.secret_provider.testing import DeterministicTestProvider

__all__ = [
    "CredentialProvider",
    "DeterministicTestProvider",
    "LocalMountedFileProvider",
    "ResolvedSecret",
    "SecretReference",
    "SecretResolutionError",
]
