"""Typed deployment-profile model and a pure honesty validator.

The two profiles from issue #950:

``single_tenant_managed``
    One customer organization per deployment/database; Keyverse or an external
    OIDC issuer with organization binding; project RBAC within that
    organization; customer-owned backup / restore / secret / network policies;
    **no cross-customer claim**. The minimum viable GA profile if proven end
    to end.

``multi_tenant_saas``
    A shared hosted service. **Not GA** until a normalized tenant authority
    exists and every authority-bearing object carries or derives an immutable
    tenant id.

:func:`validate_profile` returns human-readable problems -- it never asserts a
profile is fine, it only lists what is wrong or unproven.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: The two publishable deployment profiles.
DeploymentProfileName = Literal["single_tenant_managed", "multi_tenant_saas"]

#: How callers are authenticated.
IdentityMode = Literal["local_dev", "external_oidc", "keyverse"]

#: How tenants are separated in storage.
TenantIsolationMode = Literal[
    "single_org_per_database",
    "shared_db_tenant_scoped_rows",
]

#: Every object that must carry or derive one immutable tenant id under the
#: multi-tenant SaaS profile (issue #950).
AUTHORITY_BEARING_OBJECTS: tuple[str, ...] = (
    "project_space",
    "project_membership",
    "db_connection",
    "schema_snapshot",
    "schema_snapshot_data",
    "job_queue",
    "diagram_view",
    "table_annotation",
    "share_link",
    "api_key",
    "migration_plan",
    "migration_run",
    "connector_artifact",
    "audit_event",
    "cache_entry",
    "object_storage_key",
    "metrics_label",
    "queue_signal",
)


@dataclass(frozen=True)
class DeploymentProfile:
    """A deployment's claimed shape, checked for honesty by :func:`validate_profile`.

    Attributes:
        name: One of :data:`DeploymentProfileName`.
        identity_mode: How callers authenticate.
        tenant_isolation: How tenants are separated in storage.
        organization_binding_enforced: Whether the issuer's organization claim
            is enforced on every request.
        cross_customer_claim: Whether the deployment claims to serve more than
            one customer organization.
        customer_owned_backup_policy: Whether backup / restore / secret /
            network policy ownership is documented as the customer's.
        tenant_authority_tables_defined: Whether the normalized tenant
            authority tables exist.
        all_authority_objects_tenant_scoped: Whether every object in
            :data:`AUTHORITY_BEARING_OBJECTS` carries or derives an immutable
            tenant id.
        provisioning_lifecycle_supported: Whether tenant create / suspend /
            offboard provisioning is implemented with receipts.
        data_residency_policy_supported: Whether a per-tenant data-residency
            policy is enforced.
        ga_ready: The claim under test -- "this profile is production-ready".
    """

    name: DeploymentProfileName
    identity_mode: IdentityMode
    tenant_isolation: TenantIsolationMode
    organization_binding_enforced: bool
    cross_customer_claim: bool
    customer_owned_backup_policy: bool
    tenant_authority_tables_defined: bool
    all_authority_objects_tenant_scoped: bool
    provisioning_lifecycle_supported: bool
    data_residency_policy_supported: bool
    ga_ready: bool


#: A correct, GA-ready single-tenant profile (reference template).
PROFILE_A_TEMPLATE = DeploymentProfile(
    name="single_tenant_managed",
    identity_mode="external_oidc",
    tenant_isolation="single_org_per_database",
    organization_binding_enforced=True,
    cross_customer_claim=False,
    customer_owned_backup_policy=True,
    tenant_authority_tables_defined=False,
    all_authority_objects_tenant_scoped=False,
    provisioning_lifecycle_supported=False,
    data_residency_policy_supported=False,
    ga_ready=True,
)

#: A multi-tenant profile that is explicitly NOT GA yet (reference template).
PROFILE_B_TEMPLATE = DeploymentProfile(
    name="multi_tenant_saas",
    identity_mode="keyverse",
    tenant_isolation="shared_db_tenant_scoped_rows",
    organization_binding_enforced=True,
    cross_customer_claim=True,
    customer_owned_backup_policy=False,
    tenant_authority_tables_defined=False,
    all_authority_objects_tenant_scoped=False,
    provisioning_lifecycle_supported=False,
    data_residency_policy_supported=False,
    ga_ready=False,
)


def validate_profile(profile: DeploymentProfile) -> list[str]:
    """Return the honesty problems with ``profile`` (empty list = no problems).

    The validator never blesses a profile; it only reports what is wrong or
    unproven, so a caller can decide whether the deployment claim is truthful.
    """

    problems: list[str] = []

    if profile.name == "single_tenant_managed":
        if profile.tenant_isolation != "single_org_per_database":
            problems.append(
                "single_tenant_managed must use single_org_per_database isolation, "
                f"got {profile.tenant_isolation!r}"
            )
        if profile.cross_customer_claim:
            problems.append(
                "single_tenant_managed must not make a cross-customer claim"
            )
        if profile.ga_ready and profile.identity_mode == "local_dev":
            problems.append(
                "a GA single_tenant_managed profile must use external_oidc or "
                "keyverse identity, not local_dev"
            )
        if profile.ga_ready and not profile.organization_binding_enforced:
            problems.append(
                "a GA single_tenant_managed profile must enforce organization "
                "binding on every request"
            )
        if profile.ga_ready and not profile.customer_owned_backup_policy:
            problems.append(
                "a GA single_tenant_managed profile must document customer-owned "
                "backup / restore / secret / network policies"
            )

    elif profile.name == "multi_tenant_saas":
        if profile.tenant_isolation != "shared_db_tenant_scoped_rows":
            problems.append(
                "multi_tenant_saas must use shared_db_tenant_scoped_rows isolation, "
                f"got {profile.tenant_isolation!r}"
            )
        if profile.identity_mode == "local_dev":
            problems.append("multi_tenant_saas must not use local_dev identity")
        if profile.ga_ready:
            missing = [
                label
                for present, label in (
                    (profile.tenant_authority_tables_defined, "tenant authority tables"),
                    (
                        profile.all_authority_objects_tenant_scoped,
                        "every authority-bearing object carrying an immutable tenant id",
                    ),
                    (profile.provisioning_lifecycle_supported, "tenant provisioning lifecycle with receipts"),
                    (profile.data_residency_policy_supported, "per-tenant data-residency policy"),
                )
                if not present
            ]
            if missing:
                problems.append(
                    "multi_tenant_saas must not be marked GA until these are in "
                    "place: " + "; ".join(missing)
                )

    else:  # pragma: no cover - Literal makes this unreachable from typed callers
        problems.append(f"unknown deployment profile name: {profile.name!r}")

    return problems
