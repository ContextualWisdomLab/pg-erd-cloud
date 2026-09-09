"""Tests for :mod:`app.deploy.profile` (issue #950)."""

from __future__ import annotations

import dataclasses

from app.deploy import (
    AUTHORITY_BEARING_OBJECTS,
    PROFILE_A_TEMPLATE,
    PROFILE_B_TEMPLATE,
    validate_profile,
)


def test_reference_templates_pass_their_own_contract() -> None:
    # The GA single-tenant template is honest.
    assert validate_profile(PROFILE_A_TEMPLATE) == []
    # The multi-tenant template is explicitly NOT GA, so it is honest too.
    assert validate_profile(PROFILE_B_TEMPLATE) == []


def test_single_tenant_ga_must_not_use_local_dev_identity() -> None:
    bad = dataclasses.replace(PROFILE_A_TEMPLATE, identity_mode="local_dev")
    problems = validate_profile(bad)
    assert any("local_dev" in p for p in problems)


def test_single_tenant_must_not_make_a_cross_customer_claim() -> None:
    bad = dataclasses.replace(PROFILE_A_TEMPLATE, cross_customer_claim=True)
    assert any("cross-customer" in p for p in validate_profile(bad))


def test_single_tenant_ga_requires_org_binding_and_backup_ownership() -> None:
    bad = dataclasses.replace(
        PROFILE_A_TEMPLATE,
        organization_binding_enforced=False,
        customer_owned_backup_policy=False,
    )
    problems = validate_profile(bad)
    assert any("organization binding" in p for p in problems)
    assert any("customer-owned" in p for p in problems)


def test_single_tenant_isolation_mode_mismatch_is_flagged() -> None:
    bad = dataclasses.replace(
        PROFILE_A_TEMPLATE, tenant_isolation="shared_db_tenant_scoped_rows"
    )
    assert any("single_org_per_database" in p for p in validate_profile(bad))


def test_multi_tenant_marked_ga_without_the_authority_work_is_rejected() -> None:
    dishonest = dataclasses.replace(PROFILE_B_TEMPLATE, ga_ready=True)
    problems = validate_profile(dishonest)
    assert len(problems) == 1
    problem = problems[0]
    assert "must not be marked GA" in problem
    assert "tenant authority tables" in problem
    assert "immutable tenant id" in problem
    assert "provisioning lifecycle" in problem
    assert "data-residency" in problem


def test_multi_tenant_ga_is_accepted_once_every_requirement_is_met() -> None:
    ready = dataclasses.replace(
        PROFILE_B_TEMPLATE,
        ga_ready=True,
        tenant_authority_tables_defined=True,
        all_authority_objects_tenant_scoped=True,
        provisioning_lifecycle_supported=True,
        data_residency_policy_supported=True,
    )
    assert validate_profile(ready) == []


def test_multi_tenant_must_not_use_local_dev_identity() -> None:
    bad = dataclasses.replace(PROFILE_B_TEMPLATE, identity_mode="local_dev")
    assert any("local_dev" in p for p in validate_profile(bad))


def test_authority_object_list_covers_the_known_persisted_and_cached_objects() -> None:
    # A sample of the objects issue #950 requires to be tenant-scoped.
    for expected in (
        "schema_snapshot",
        "schema_snapshot_data",
        "share_link",
        "api_key",
        "job_queue",
        "queue_signal",
        "object_storage_key",
        "metrics_label",
    ):
        assert expected in AUTHORITY_BEARING_OBJECTS
    # No duplicates.
    assert len(AUTHORITY_BEARING_OBJECTS) == len(set(AUTHORITY_BEARING_OBJECTS))
