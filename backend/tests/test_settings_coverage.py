"""Fail-closed coverage for application secret-file settings validation."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import settings as settings_module
from app.settings import Settings


@dataclass
class _PathPolicy:
    """Mutable fake-path policy used to exercise secret-file validation branches."""

    missing: bool = False
    symlink: bool = False
    inside_allowed_base: bool = True
    regular_file: bool = True
    content: str = "buyer-secret\n"


class _FakePath:
    """Path-like object implementing only the secret validator's trusted operations."""

    def __init__(self, raw: str, policy: _PathPolicy) -> None:
        self.raw = raw
        self.policy = policy

    def __str__(self) -> str:
        """Return the represented path text for bounded validation messages."""
        return self.raw

    def resolve(self, *, strict: bool = False) -> "_FakePath":
        """Resolve the fake path or raise when the target is configured missing."""
        if strict and self.raw != "/run/secrets" and self.policy.missing:
            raise FileNotFoundError(self.raw)
        return self

    def is_symlink(self) -> bool:
        """Return whether the configured target is a symbolic link."""
        return self.raw != "/run/secrets" and self.policy.symlink

    def is_relative_to(self, other: "_FakePath") -> bool:
        """Report whether the target belongs to the reviewed secret mount."""
        assert other.raw == "/run/secrets"
        return self.policy.inside_allowed_base

    def is_file(self) -> bool:
        """Return whether the configured target is a regular file."""
        return self.policy.regular_file

    def read_text(self, *, encoding: str) -> str:
        """Return the configured UTF-8 secret material."""
        assert encoding == "utf-8"
        return self.policy.content


def _install_fake_path(
    monkeypatch: pytest.MonkeyPatch,
    policy: _PathPolicy,
) -> None:
    """Replace pathlib construction inside the settings module with one policy."""

    def path_factory(raw: object) -> _FakePath:
        return _FakePath(str(raw), policy)

    monkeypatch.setattr(settings_module, "Path", path_factory)


def test_secret_file_validator_passes_through_non_mapping_and_missing_selector() -> None:
    """Leave non-mapping input and mappings without APP_SECRET_FILE untouched."""
    marker = object()
    assert Settings._load_app_secret_from_file(marker) is marker

    data = {"app_secret": "direct-secret"}
    assert Settings._load_app_secret_from_file(data) is data


@pytest.mark.parametrize(
    ("policy", "message"),
    [
        (_PathPolicy(missing=True), "does not exist"),
        (_PathPolicy(symlink=True), "must not be a symlink"),
        (_PathPolicy(inside_allowed_base=False), "must be under"),
        (_PathPolicy(regular_file=False), "does not exist or is not a file"),
        (_PathPolicy(content="\r\n"), "is empty"),
    ],
)
def test_secret_file_validator_rejects_unsafe_file_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    policy: _PathPolicy,
    message: str,
) -> None:
    """Reject missing, linked, out-of-root, non-file, and empty secret material."""
    _install_fake_path(monkeypatch, policy)

    with pytest.raises(ValueError, match=message):
        Settings._load_app_secret_from_file(
            {
                "app_secret": "must-be-replaced",
                "APP_SECRET_FILE": "/run/secrets/app_secret",
            }
        )


def test_secret_file_validator_prefers_trimmed_file_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read the reviewed secret file, strip only line endings, and preserve input immutably."""
    policy = _PathPolicy(content="  file-secret  \r\n")
    _install_fake_path(monkeypatch, policy)
    original = {
        "app_secret": "direct-secret",
        "app_secret_file": "/run/secrets/app_secret",
        "database_url": "postgresql://db/app",
    }

    result = Settings._load_app_secret_from_file(original)

    assert result is not original
    assert result["app_secret"] == "  file-secret  "
    assert original["app_secret"] == "direct-secret"
    assert result["database_url"] == "postgresql://db/app"
