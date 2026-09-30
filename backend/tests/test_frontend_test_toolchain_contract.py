"""Contracts for the frontend test toolchain dependency family."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPOSITORY_ROOT / "frontend"


def _read_json_document(document_path: Path) -> dict[str, Any]:
    """Return one repository JSON document."""

    return json.loads(document_path.read_text(encoding="utf-8"))


class FrontendTestToolchainContractTest(unittest.TestCase):
    """Verify the frontend test packages remain installable together."""

    def test_vitest_runtime_and_coverage_provider_share_exact_version(self) -> None:
        """Keep Vitest and its V8 coverage provider on one exact release line."""

        package_manifest = _read_json_document(FRONTEND_ROOT / "package.json")
        package_lock = _read_json_document(FRONTEND_ROOT / "package-lock.json")

        manifest_dependencies = package_manifest["devDependencies"]
        locked_packages = package_lock["packages"]
        root_dependencies = locked_packages[""]["devDependencies"]
        vitest_package = locked_packages["node_modules/vitest"]
        coverage_package = locked_packages["node_modules/@vitest/coverage-v8"]

        self.assertEqual(
            manifest_dependencies["vitest"],
            manifest_dependencies["@vitest/coverage-v8"],
        )
        self.assertEqual(
            root_dependencies["vitest"],
            root_dependencies["@vitest/coverage-v8"],
        )
        self.assertEqual(vitest_package["version"], coverage_package["version"])
        self.assertEqual(
            coverage_package["peerDependencies"]["vitest"],
            vitest_package["version"],
        )
