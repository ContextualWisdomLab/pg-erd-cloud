"""Tests for the ``app.secret_provider`` credential-provider boundary (issue #946)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from app.secret_provider import (
    CredentialProvider,
    DeterministicTestProvider,
    LocalMountedFileProvider,
    ResolvedSecret,
    SecretReference,
    SecretResolutionError,
)

_SECRET = "correct horse battery staple \U0001f510"


def _ref(name: str, *, provider: str = "local_secret_file") -> SecretReference:
    return SecretReference(name=name, purpose="app_secret", provider=provider)


def _write(base: Path, name: str, data: bytes) -> Path:
    path = base / name
    path.write_bytes(data)
    return path


def test_local_provider_reads_a_plain_file_and_trims_one_newline(tmp_path: Path) -> None:
    _write(tmp_path, "app_secret", (_SECRET + "\n").encode("utf-8"))
    provider = LocalMountedFileProvider(tmp_path)
    resolved = provider.resolve(_ref("app_secret"))
    assert isinstance(resolved, ResolvedSecret)
    assert resolved.reveal() == _SECRET
    assert resolved.audit_reference and len(resolved.audit_reference) == 16
    # Only ONE trailing newline is stripped.
    _write(tmp_path, "two_nl", (_SECRET + "\n\n").encode("utf-8"))
    assert provider.resolve(_ref("two_nl")).reveal() == _SECRET + "\n"


@pytest.mark.parametrize(
    "name,make,reason",
    [
        ("missing", None, "not found"),
        ("empty", b"", "empty"),
        ("oversized", b"x" * (64 * 1024 + 1), "bytes"),
        ("bad_utf8", b"\xff\xfe\x00", "UTF-8"),
        ("only_newline", b"\n", "no content after trimming"),
    ],
)
def test_local_provider_fails_closed(tmp_path: Path, name, make, reason) -> None:
    if make is not None:
        _write(tmp_path, name, make)
    provider = LocalMountedFileProvider(tmp_path)
    with pytest.raises(SecretResolutionError) as exc:
        provider.resolve(_ref(name))
    assert reason in str(exc.value)


def test_local_provider_rejects_symlink(tmp_path: Path) -> None:
    real = _write(tmp_path.parent, "outside_secret", _SECRET.encode())
    link = tmp_path / "linked"
    os.symlink(real, link)
    with pytest.raises(SecretResolutionError, match="symlink"):
        LocalMountedFileProvider(tmp_path).resolve(_ref("linked"))


def test_local_provider_rejects_path_escape_and_multi_segment_names(tmp_path: Path) -> None:
    provider = LocalMountedFileProvider(tmp_path)
    for bad in ["../etc/passwd", "sub/dir", "/abs/path", "", ".."]:
        with pytest.raises(SecretResolutionError):
            provider.resolve(_ref(bad))


def test_local_provider_rejects_a_directory(tmp_path: Path) -> None:
    (tmp_path / "a_dir").mkdir()
    with pytest.raises(SecretResolutionError):
        LocalMountedFileProvider(tmp_path).resolve(_ref("a_dir"))


def test_local_provider_rejects_reference_for_another_provider(tmp_path: Path) -> None:
    _write(tmp_path, "app_secret", _SECRET.encode())
    with pytest.raises(SecretResolutionError, match="provider"):
        LocalMountedFileProvider(tmp_path).resolve(
            _ref("app_secret", provider="org_credential_registry")
        )


def test_deterministic_test_provider_happy_and_missing() -> None:
    provider = DeterministicTestProvider({"app_secret": _SECRET})
    ref = SecretReference(name="app_secret", purpose="app_secret", provider="deterministic_test")
    first = provider.resolve(ref)
    second = provider.resolve(ref)
    assert first.reveal() == _SECRET
    assert first == second  # deterministic: same value, same timestamp
    with pytest.raises(SecretResolutionError, match="not known"):
        provider.resolve(SecretReference(name="absent", purpose="x", provider="deterministic_test"))


def test_both_providers_satisfy_the_protocol(tmp_path: Path) -> None:
    assert isinstance(LocalMountedFileProvider(tmp_path), CredentialProvider)
    assert isinstance(DeterministicTestProvider({}), CredentialProvider)


def test_resolved_secret_value_never_appears_in_str_repr_format_or_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(tmp_path, "app_secret", _SECRET.encode())
    resolved = LocalMountedFileProvider(tmp_path).resolve(_ref("app_secret"))

    assert _SECRET not in str(resolved)
    assert _SECRET not in repr(resolved)
    assert _SECRET not in f"{resolved}"
    assert _SECRET not in f"{resolved!r}"
    assert _SECRET not in "%s" % (resolved,)
    assert _SECRET not in "%r" % (resolved,)
    assert "REDACTED" in str(resolved)

    logger = logging.getLogger("test.credential")
    with caplog.at_level(logging.INFO, logger="test.credential"):
        logger.info("resolved secret %s / %r", resolved, resolved)
    assert _SECRET not in caplog.text

    # The value is still retrievable through the explicit accessor.
    assert resolved.reveal() == _SECRET


def test_secret_reference_str_carries_no_value() -> None:
    ref = SecretReference(name="app_secret", purpose="app_secret", provider="p", version="v3")
    text = str(ref)
    assert "app_secret" in text and "v3" in text
    assert "value" not in text.lower()
