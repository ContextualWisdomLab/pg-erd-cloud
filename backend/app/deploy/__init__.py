"""GA deployment profiles, tenant isolation, and lifecycle provisioning (#950).

pg-erd-cloud must make a *truthful* deployment claim: either a single-tenant /
self-hosted GA profile with explicit boundaries, or a multi-tenant SaaS
profile with enforced tenant ownership on every persisted and cached object.
It must never imply multi-tenancy merely because projects have members.

This first increment ships the typed profile model and a pure validator that
rejects a dishonest or under-specified profile. No infrastructure, no
``Settings`` wiring, no migration.
"""

from app.deploy.profile import (
    AUTHORITY_BEARING_OBJECTS,
    PROFILE_A_TEMPLATE,
    PROFILE_B_TEMPLATE,
    DeploymentProfile,
    validate_profile,
)

__all__ = [
    "AUTHORITY_BEARING_OBJECTS",
    "PROFILE_A_TEMPLATE",
    "PROFILE_B_TEMPLATE",
    "DeploymentProfile",
    "validate_profile",
]
