"""Assemble the immutable release-evidence manifest (issue #953).

A commercial release is only credible when inclusion, dependency pinning,
migration compatibility, exact-head provenance, and known limitations can be
stated from **one immutable manifest**. This module builds that manifest
from facts the caller has already gathered — it runs no git, no network, no
filesystem access.

The manifest is honest by construction: ``is_ga_candidate`` is ``True``
only when ``known_limitations`` is empty. Listing a limitation is the
supported way to ship a beta / non-GA artifact without the manifest
claiming otherwise.

References (APA 7th):

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1* (NIST Special Publication
800-218). https://doi.org/10.6028/NIST.SP.800-218

SLSA Community. (2025). *Supply-chain levels for software artifacts
specification, version 1.2*. https://slsa.dev/spec/v1.2/
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

#: Manifest contract version. Bump on any breaking change to the output shape.
MANIFEST_VERSION = "1"

_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_str(value: object, field: str) -> str:
    """Return ``value`` as a non-empty stripped string or raise ``ValueError``."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def build_release_manifest(
    *,
    source_commit: str,
    backend_version: str,
    frontend_version: str,
    migration_revisions: list[str],
    dependency_lock_digests: dict[str, str],
    included_prs: list[int],
    known_limitations: list[str],
    generated_at: str,
) -> dict[str, Any]:
    """Validate the supplied release facts and return the immutable manifest.

    Args:
        source_commit: The exact commit the release is cut from. Lowercased,
            then must match ``^[0-9a-f]{7,40}$``.
        backend_version: Backend package version; must match
            ``^\\d+\\.\\d+\\.\\d+`` (a trailing pre-release suffix is allowed).
        frontend_version: Frontend package version; same rule.
        migration_revisions: Alembic revision ids included in the release.
            Every item must be a non-empty string; the output is sorted and
            de-duplicated.
        dependency_lock_digests: ``{lockfile_name: "sha256:<64 hex>"}``. Keys
            must be non-empty strings; every value must match
            ``^sha256:[0-9a-f]{64}$``. The output dict has sorted keys.
        included_prs: PR numbers merged into the release. Every item must be
            an ``int`` greater than 0; the output is sorted and de-duplicated.
        known_limitations: Human-readable statements of what is *not* GA in
            this release. Every item must be a non-empty string; order is
            preserved. A non-empty list forces ``is_ga_candidate`` to
            ``False``.
        generated_at: When this manifest was assembled. Must be parseable by
            :meth:`datetime.datetime.fromisoformat` and timezone-aware.

    Returns:
        A JSON-serializable dict with ``manifest_version``, the validated
        ``source_commit`` (lowercased), ``backend_version``,
        ``frontend_version``, the normalized ``migration_revisions`` /
        ``dependency_lock_digests`` / ``included_prs``, ``known_limitations``,
        ``generated_at``, and ``is_ga_candidate`` (``len(known_limitations)
        == 0``). Deterministic for a given input.

    Raises:
        ValueError: Naming the first field that fails validation.
    """
    commit = _require_str(source_commit, "source_commit").lower()
    if not _COMMIT_RE.match(commit):
        raise ValueError("source_commit must be 7-40 lowercase hex characters")

    backend = _require_str(backend_version, "backend_version")
    if not _VERSION_RE.match(backend):
        raise ValueError("backend_version must look like N.N.N")
    frontend = _require_str(frontend_version, "frontend_version")
    if not _VERSION_RE.match(frontend):
        raise ValueError("frontend_version must look like N.N.N")

    revisions: set[str] = set()
    for revision in migration_revisions:
        revisions.add(_require_str(revision, "migration_revisions[]"))

    digests: dict[str, str] = {}
    for name, digest in dependency_lock_digests.items():
        key = _require_str(name, "dependency_lock_digests key")
        if not isinstance(digest, str) or not _DIGEST_RE.match(digest):
            raise ValueError(
                f"dependency_lock_digests[{key!r}] must match 'sha256:<64 hex>'"
            )
        digests[key] = digest

    prs: set[int] = set()
    for pr in included_prs:
        if not isinstance(pr, int) or isinstance(pr, bool) or pr <= 0:
            raise ValueError("included_prs items must be positive integers")
        prs.add(pr)

    limitations: list[str] = [
        _require_str(item, "known_limitations[]") for item in known_limitations
    ]

    stamp = _require_str(generated_at, "generated_at")
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError as exc:
        raise ValueError("generated_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")

    return {
        "manifest_version": MANIFEST_VERSION,
        "source_commit": commit,
        "backend_version": backend,
        "frontend_version": frontend,
        "migration_revisions": sorted(revisions),
        "dependency_lock_digests": {k: digests[k] for k in sorted(digests)},
        "included_prs": sorted(prs),
        "known_limitations": limitations,
        "generated_at": stamp,
        "is_ga_candidate": len(limitations) == 0,
    }
