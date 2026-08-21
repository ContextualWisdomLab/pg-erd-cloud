from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import settings as settings_module
from app.settings import Settings


def test_secret_file_is_read_from_anchored_directory(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "app_secret"
    secret_file.write_text("trusted-secret\r\n", encoding="utf-8")

    assert settings_module._read_secret_file(
        secret_file,
        allowed_base=secrets_dir,
    ) == "trusted-secret"


def test_secret_file_must_be_a_direct_child(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    nested_dir = secrets_dir / "nested"
    nested_dir.mkdir(parents=True)
    nested_secret = nested_dir / "app_secret"
    nested_secret.write_text("trusted-secret", encoding="utf-8")

    with pytest.raises(ValueError, match="must be a direct child"):
        settings_module._read_secret_file(
            nested_secret,
            allowed_base=secrets_dir,
        )


def test_secret_file_must_be_regular(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    directory_named_as_secret = secrets_dir / "app_secret"
    directory_named_as_secret.mkdir()

    with pytest.raises(ValueError, match="must be a regular file"):
        settings_module._read_secret_file(
            directory_named_as_secret,
            allowed_base=secrets_dir,
        )


def test_secret_file_must_not_be_empty(tmp_path: Path) -> None:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "app_secret"
    secret_file.write_text("\r\n", encoding="utf-8")

    with pytest.raises(ValueError, match="APP_SECRET_FILE is empty"):
        settings_module._read_secret_file(
            secret_file,
            allowed_base=secrets_dir,
        )


def test_settings_prefers_secret_from_secure_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_path = Path("/run/secrets/app_secret")
    monkeypatch.setattr(
        settings_module,
        "_read_secret_file",
        lambda path: "file-secret" if path == secret_path else "unexpected",
    )

    configured = Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://user:pass@db/app",
            "app_secret": "environment-secret",
            "APP_SECRET_FILE": str(secret_path),
        }
    )

    assert configured.app_secret == "file-secret"


def test_secret_file_replacement_with_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never follow a leaf swapped between validation and the guarded open."""

    read_secret_file = settings_module._read_secret_file

    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    secret_file = secrets_dir / "app_secret"
    secret_file.write_text("trusted-secret\n", encoding="utf-8")
    attacker_file = tmp_path / "attacker-secret"
    attacker_file.write_text("stolen-secret\n", encoding="utf-8")

    real_open = os.open

    def racing_open(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        if path == secret_file.name and dir_fd is not None:
            secret_file.unlink()
            secret_file.symlink_to(attacker_file)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(settings_module.os, "open", racing_open)

    with pytest.raises(ValueError, match="could not be opened securely"):
        read_secret_file(secret_file, allowed_base=secrets_dir)
