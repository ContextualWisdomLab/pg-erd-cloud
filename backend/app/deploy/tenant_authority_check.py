"""Tenant-authority column-presence check for the multi-tenant profile.

:mod:`app.deploy.profile` models a deployment's claimed shape and carries a
single boolean, ``all_authority_objects_tenant_scoped``, that
:func:`app.deploy.profile.validate_profile` trusts when it decides whether a
``multi_tenant_saas`` profile may claim GA readiness. That boolean has to be
*earned* by the schema, not asserted.

This module is the concrete check behind it. Given a description of the
persisted tables, it verifies that every object in
:data:`app.deploy.profile.AUTHORITY_BEARING_OBJECTS` either carries an
immutable ``tenant_account_uuid`` column or explicitly derives its tenant
from another object. It reports exactly which objects fail and why, so the
gap is actionable rather than a single red boolean.

For the ``single_org_per_database`` isolation mode the check is not
applicable: one customer organization per database means there is no
cross-tenant row to scope. The function says so rather than pretending to
pass.

The check is pure -- no database, no ``Settings``, no migration. It works
from a list of table descriptions the caller assembles (from the ORM
metadata, an Alembic autogenerate diff, or an introspection snapshot).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.deploy.profile import AUTHORITY_BEARING_OBJECTS, TenantIsolationMode

#: Contract version for the returned report shape.
CHECK_VERSION = "1"

#: The column every tenant-scoped authority object must carry directly.
TENANT_KEY_COLUMN = "tenant_account_uuid"

#: Isolation modes this check understands (mirrors
#: :data:`app.deploy.profile.TenantIsolationMode`).
_KNOWN_ISOLATION_MODES = ("single_org_per_database", "shared_db_tenant_scoped_rows")


def _definition_index(
    table_definitions: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    """Index table descriptions by name; collect names not in the authority set.

    Each description is ``{"name": str, "columns": Iterable[str],
    "derives_tenant_from": str | None}``. Entries with no usable ``name`` are
    skipped. The second return value lists described tables that are not in
    :data:`AUTHORITY_BEARING_OBJECTS` (informational, never a failure).
    """
    by_name: dict[str, Mapping[str, Any]] = {}
    unknown: list[str] = []
    authority = set(AUTHORITY_BEARING_OBJECTS)
    for definition in table_definitions:
        name = definition.get("name")
        if not name:
            continue
        name = str(name)
        by_name[name] = definition
        if name not in authority:
            unknown.append(name)
    return by_name, sorted(unknown)


def check_tenant_authority(
    table_definitions: Iterable[Mapping[str, Any]],
    *,
    tenant_isolation: TenantIsolationMode,
) -> dict[str, Any]:
    """Check that every authority-bearing object is tenant-scoped.

    Args:
        table_definitions: An iterable of table descriptions, each a mapping
            ``{"name": str, "columns": Iterable[str], "derives_tenant_from":
            str | None}``. ``columns`` is the set of column names on the
            table; ``derives_tenant_from`` names another object this table
            reaches its tenant through (e.g. a child row scoped by its
            parent), or is absent / ``None`` when the table must carry the
            key itself.
        tenant_isolation: The deployment's isolation mode. For
            ``single_org_per_database`` the check is not applicable and
            returns ``applicable=False`` with ``compliant=True``.

    Returns:
        A report mapping with:

        ``version``
            :data:`CHECK_VERSION`.
        ``isolation_mode``
            The ``tenant_isolation`` argument, echoed back.
        ``applicable``
            ``False`` for ``single_org_per_database``, ``True`` otherwise.
        ``compliant``
            ``True`` when every authority object is defined and either
            carries :data:`TENANT_KEY_COLUMN` or declares
            ``derives_tenant_from``. Always ``True`` when not applicable.
        ``not_applicable_reason``
            Present only when ``applicable`` is ``False``.
        ``required_object_count``
            ``len(AUTHORITY_BEARING_OBJECTS)``.
        ``carrying`` / ``derived`` / ``missing_scoping`` / ``missing_definition``
            Sorted lists partitioning the authority objects. ``derived``
            entries are ``{"object": str, "via": str}``.
        ``unknown_tables``
            Described tables that are not authority-bearing (informational).

    Raises:
        ValueError: If ``tenant_isolation`` is not a known isolation mode.
    """
    if tenant_isolation not in _KNOWN_ISOLATION_MODES:
        raise ValueError(
            f"unknown tenant_isolation {tenant_isolation!r}; "
            f"expected one of {_KNOWN_ISOLATION_MODES}"
        )

    by_name, unknown = _definition_index(table_definitions)

    if tenant_isolation == "single_org_per_database":
        return {
            "version": CHECK_VERSION,
            "isolation_mode": tenant_isolation,
            "applicable": False,
            "compliant": True,
            "not_applicable_reason": (
                "single_org_per_database isolates each customer organization "
                "in its own database, so there is no cross-tenant row to "
                "scope; row-level tenant keys are not required."
            ),
            "required_object_count": len(AUTHORITY_BEARING_OBJECTS),
            "carrying": [],
            "derived": [],
            "missing_scoping": [],
            "missing_definition": [],
            "unknown_tables": unknown,
        }

    carrying: list[str] = []
    derived: list[dict[str, str]] = []
    missing_scoping: list[str] = []
    missing_definition: list[str] = []

    for obj in AUTHORITY_BEARING_OBJECTS:
        definition = by_name.get(obj)
        if definition is None:
            missing_definition.append(obj)
            continue
        columns = {str(c) for c in definition.get("columns") or ()}
        derives_from = definition.get("derives_tenant_from")
        if TENANT_KEY_COLUMN in columns:
            carrying.append(obj)
        elif derives_from:
            derived.append({"object": obj, "via": str(derives_from)})
        else:
            missing_scoping.append(obj)

    compliant = not missing_scoping and not missing_definition

    return {
        "version": CHECK_VERSION,
        "isolation_mode": tenant_isolation,
        "applicable": True,
        "compliant": compliant,
        "required_object_count": len(AUTHORITY_BEARING_OBJECTS),
        "carrying": sorted(carrying),
        "derived": sorted(derived, key=lambda d: d["object"]),
        "missing_scoping": sorted(missing_scoping),
        "missing_definition": sorted(missing_definition),
        "unknown_tables": unknown,
    }
