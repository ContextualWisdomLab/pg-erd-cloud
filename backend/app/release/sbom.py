"""Build a CycloneDX 1.6 SBOM from the lockfiles already in the repo.

A software bill of materials (SBOM) lists every third-party component that
ships inside a release, so a buyer's security team can match it against
vulnerability feeds and license policy. This module produces one **from the
lockfiles the repo already commits** -- the hash-locked pip/uv requirements
lock and the npm ``package-lock.json`` -- by pure text/JSON parsing. It never
runs ``pip``/``npm``, never resolves a dependency graph, and never touches
the network: whatever the lockfile pins is exactly what the SBOM reports.

Public functions:

* :func:`parse_pip_lock` -- turn a requirements lock's text into component
  dicts (name, version, ``pkg:pypi`` purl, SHA-256 hashes).
* :func:`parse_npm_lock` -- turn a parsed ``package-lock.json`` (v2/v3, which
  carries a ``packages`` map) into component dicts (name, version,
  ``pkg:npm`` purl, integrity hash).
* :func:`build_sbom` -- merge both into one CycloneDX 1.6 ``bom`` document
  with the components de-duplicated by purl and stably sorted.

Deferred (tracked on issue #953): signing the SBOM, attaching it to the
release manifest built by :mod:`app.release.manifest`, and emitting VEX
(exploitability) statements.

References (APA 7th):

* OWASP Foundation. (2024). *CycloneDX specification 1.6*.
  https://cyclonedx.org/docs/1.6/
* National Telecommunications and Information Administration. (2021). *The
  minimum elements for a software bill of materials (SBOM)*. U.S. Department
  of Commerce.
  https://www.ntia.gov/report/2021/minimum-elements-software-bill-materials-sbom
"""

from __future__ import annotations

import re
from typing import Any

SBOM_SPEC_VERSION = "1.6"
"""The CycloneDX schema version emitted by :func:`build_sbom`."""

_PIP_HASH_RE = re.compile(r"--hash=sha256:([0-9a-fA-F]{64})")
_PIP_NAME_VERSION_RE = re.compile(r"^([A-Za-z0-9._-]+)\s*==\s*([^\s;]+)")


def _require_non_empty_str(value: object, field: str) -> str:
    """Return ``value`` unchanged, or raise :class:`ValueError` naming ``field``."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _logical_lines(text: str) -> list[str]:
    """Join ``\\``-continued lines so one requirement is one string."""

    joined = text.replace("\\\n", " ").replace("\\\r\n", " ")
    return joined.splitlines()


def parse_pip_lock(text: str) -> list[dict[str, Any]]:
    """Parse a pip / uv requirements lock into CycloneDX component dicts.

    Recognises ``name==version`` requirements (the form every hash-locked
    lockfile uses) and collects the ``--hash=sha256:<hex>`` values that
    follow, whether on the same line or on ``\\``-continued lines. Blank
    lines, ``#`` comments, and option lines (anything starting with ``-``)
    are skipped.

    Args:
        text: The full lockfile text.

    Returns:
        One dict per requirement: ``{"type": "library", "name", "version",
        "purl": "pkg:pypi/<name>@<version>", "hashes": [{"alg": "SHA-256",
        "content": <hex>}, ...]}``. Order follows the file.
    """

    components: list[dict[str, Any]] = []
    for raw in _logical_lines(text):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _PIP_NAME_VERSION_RE.match(line)
        if match is None:
            continue
        name, version = match.group(1), match.group(2)
        hashes = [
            {"alg": "SHA-256", "content": h.lower()}
            for h in _PIP_HASH_RE.findall(line)
        ]
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:pypi/{name}@{version}",
                "hashes": hashes,
            }
        )
    return components


def _npm_name_from_key(key: str) -> str | None:
    """Return the package name for a ``package-lock.json`` ``packages`` key.

    ``"node_modules/foo"`` -> ``"foo"``; ``"node_modules/@scope/bar"`` ->
    ``"@scope/bar"``; nested ``".../node_modules/baz"`` -> ``"baz"``. Keys
    without a ``node_modules/`` segment (the root ``""`` and workspace
    entries) return ``None`` so the caller skips them.
    """

    marker = "node_modules/"
    if marker not in key:
        return None
    return key.rsplit(marker, 1)[1]


def _npm_hashes(integrity: object) -> list[dict[str, str]]:
    """Turn an npm ``integrity`` string (``sha512-<b64>``) into hash dicts."""

    if not isinstance(integrity, str) or "-" not in integrity:
        return []
    algo, _, content = integrity.partition("-")
    alg_map = {"sha512": "SHA-512", "sha384": "SHA-384", "sha256": "SHA-256"}
    if algo not in alg_map or not content:
        return []
    return [{"alg": alg_map[algo], "content": content}]


def parse_npm_lock(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse a parsed ``package-lock.json`` (v2/v3) into component dicts.

    Walks ``obj["packages"]``, skips the root key ``""`` and any entry with
    no ``version`` (workspace links, bundled placeholders), and emits one
    component per installed ``node_modules`` package.

    Args:
        obj: The already-``json.load``ed lockfile. Must be a dict; a
            ``packages`` key is expected (an absent one yields ``[]``).

    Returns:
        One dict per package: ``{"type": "library", "name", "version",
        "purl": "pkg:npm/<name>@<version>", "hashes": [...]}``.

    Raises:
        ValueError: If ``obj`` is not a dict.
    """

    if not isinstance(obj, dict):
        raise ValueError("npm_lock must be a parsed JSON object (dict)")
    packages = obj.get("packages")
    if not isinstance(packages, dict):
        return []

    components: list[dict[str, Any]] = []
    for key, entry in packages.items():
        if key == "" or not isinstance(entry, dict):
            continue
        name = _npm_name_from_key(key)
        version = entry.get("version")
        if name is None or not isinstance(version, str) or not version:
            continue
        components.append(
            {
                "type": "library",
                "name": name,
                "version": version,
                "purl": f"pkg:npm/{name}@{version}",
                "hashes": _npm_hashes(entry.get("integrity")),
            }
        )
    return components


def build_sbom(
    *,
    pip_lock: str,
    npm_lock: dict[str, Any],
    component_name: str,
    component_version: str,
    generated_at: str,
) -> dict[str, Any]:
    """Merge the pip and npm components into one CycloneDX 1.6 ``bom``.

    Args:
        pip_lock: Requirements-lock text (see :func:`parse_pip_lock`).
        npm_lock: Parsed ``package-lock.json`` (see :func:`parse_npm_lock`).
        component_name: Name of the application this SBOM describes.
        component_version: Its version string.
        generated_at: SBOM timestamp, recorded verbatim (an ISO-8601 string
            is expected; this function does not parse it).

    Returns:
        ``{"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
        "metadata": {"timestamp", "component": {...}}, "components": [...]}``
        with components de-duplicated by ``purl`` and sorted by
        ``(type, name, version)``.

    Raises:
        ValueError: If ``component_name``, ``component_version``, or
            ``generated_at`` is blank, or if ``npm_lock`` is not a dict.
    """

    name = _require_non_empty_str(component_name, "component_name")
    version = _require_non_empty_str(component_version, "component_version")
    timestamp = _require_non_empty_str(generated_at, "generated_at")

    merged: dict[str, dict[str, Any]] = {}
    for component in [*parse_pip_lock(pip_lock), *parse_npm_lock(npm_lock)]:
        merged.setdefault(component["purl"], component)

    components = sorted(
        merged.values(), key=lambda c: (c["type"], c["name"], c["version"])
    )
    return {
        "bomFormat": "CycloneDX",
        "specVersion": SBOM_SPEC_VERSION,
        "version": 1,
        "metadata": {
            "timestamp": timestamp,
            "component": {
                "type": "application",
                "name": name,
                "version": version,
            },
        },
        "components": components,
    }
