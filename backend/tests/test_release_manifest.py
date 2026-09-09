"""Tests for :mod:`app.release.manifest`.

The assembler must validate every field, normalize collections, be honest
about GA candidacy, and produce a deterministic JSON-serializable manifest.
"""

from __future__ import annotations

import json

import pytest

from app.release.manifest import MANIFEST_VERSION, build_release_manifest

_GOOD = dict(
    source_commit="8dc746920c12988f082e914879d95e13c9693535",
    backend_version="0.1.0",
    frontend_version="0.1.0",
    migration_revisions=["0002_add_lineage", "0001_init"],
    dependency_lock_digests={
        "requirements.lock": "sha256:" + "a" * 64,
        "package-lock.json": "sha256:" + "b" * 64,
    },
    included_prs=[1024, 942, 1024],
    known_limitations=[],
    generated_at="2026-09-02T10:00:00+00:00",
)


def _manifest(**overrides: object) -> dict:
    return build_release_manifest(**{**_GOOD, **overrides})  # type: ignore[arg-type]


def test_happy_path_is_a_ga_candidate() -> None:
    manifest = _manifest()
    assert manifest["manifest_version"] == MANIFEST_VERSION
    assert manifest["is_ga_candidate"] is True
    assert manifest["source_commit"] == _GOOD["source_commit"]


def test_a_known_limitation_disqualifies_ga() -> None:
    manifest = _manifest(
        known_limitations=["Persistent migration apply is disabled (non-GA)."]
    )
    assert manifest["is_ga_candidate"] is False
    assert manifest["known_limitations"] == [
        "Persistent migration apply is disabled (non-GA)."
    ]


def test_migration_revisions_are_sorted_and_deduped() -> None:
    manifest = _manifest(migration_revisions=["b", "a", "a"])
    assert manifest["migration_revisions"] == ["a", "b"]


def test_included_prs_are_sorted_and_deduped() -> None:
    manifest = _manifest(included_prs=[3, 1, 1])
    assert manifest["included_prs"] == [1, 3]


def test_dependency_lock_digests_keys_are_sorted() -> None:
    manifest = _manifest(
        dependency_lock_digests={
            "z.lock": "sha256:" + "c" * 64,
            "a.lock": "sha256:" + "d" * 64,
        }
    )
    assert list(manifest["dependency_lock_digests"]) == ["a.lock", "z.lock"]


def test_bad_source_commit_raises_naming_the_field() -> None:
    with pytest.raises(ValueError, match="source_commit"):
        _manifest(source_commit="xyz")


def test_bad_backend_version_raises() -> None:
    with pytest.raises(ValueError, match="backend_version"):
        _manifest(backend_version="1.0")


def test_digest_without_sha256_prefix_raises() -> None:
    with pytest.raises(ValueError, match="dependency_lock_digests"):
        _manifest(dependency_lock_digests={"requirements.lock": "deadbeef"})


def test_non_positive_pr_number_raises() -> None:
    with pytest.raises(ValueError, match="included_prs"):
        _manifest(included_prs=[0])


def test_naive_generated_at_raises() -> None:
    with pytest.raises(ValueError, match="generated_at"):
        _manifest(generated_at="2026-09-02T10:00:00")


def test_manifest_round_trips_through_json() -> None:
    manifest = _manifest()
    assert json.loads(json.dumps(manifest)) == manifest


def test_build_is_deterministic() -> None:
    assert _manifest() == _manifest()
