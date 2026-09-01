"""Typed lifecycle records for snapshot lineage and promotion.

These are the field contracts a later increment will persist as normalized
tables. They are ``TypedDict`` / ``Literal`` shapes only -- no behaviour, no
I/O -- so the algorithms in :mod:`app.lineage.derive`,
:mod:`app.lineage.promote`, and :mod:`app.lineage.retention` (and, later, the
Alembic migration) all agree on one contract.

DB object names follow the project rule: two-or-more-word ``snake_case``.
"""

from __future__ import annotations

from typing import Literal, TypedDict

#: The typed parent -> child derivation edges. One generic "derived from" edge
#: is deliberately not allowed: a diff and an export relate two snapshots very
#: differently.
DerivationKind = Literal[
    "captured_from",
    "imported_from",
    "normalized_from",
    "compared_with",
    "exported_from",
    "planned_from",
]

#: Environment codes for a promotion. Not tied to any customer's naming.
PromotionEnvironment = Literal["development", "staging", "production"]

#: Lifecycle state of a promotion record.
PromotionState = Literal["promoted", "superseded", "rejected"]

#: What a retention decision concludes. A decision is a *record*, never a
#: side-effecting delete.
RetentionDisposition = Literal[
    "retain",
    "archive_eligible",
    "delete_eligible",
    "legal_hold",
]


class SnapshotLineage(TypedDict):
    """Immutable identity + bitemporal facts for one schema snapshot.

    Keys:
        snapshot_id: Stable id of the snapshot.
        content_hash: Canonical content hash of the snapshot payload.
        source_dialect: Target dialect (e.g. ``postgresql``).
        source_version: Target server version string.
        connection_reference: Opaque id of the connection it was captured from.
        schema_scope: The schema filter / scope the snapshot represents.
        capture_tool_version: Version of the introspection tool used.
        captured_at: When the target metadata was observed.
        available_at: When the completed snapshot became usable.
        valid_from: When a promoted baseline is declared applicable (or None).
        valid_to: End of that applicability interval (None = still effective).
        recorded_at: When pg-erd-cloud learned this declaration.
        superseded_at: When this declaration was changed (or None).
        knowledge_cutoff: Latest evidence allowed in an audit/export from it.
    """

    snapshot_id: str
    content_hash: str
    source_dialect: str
    source_version: str
    connection_reference: str
    schema_scope: str
    capture_tool_version: str
    captured_at: str
    available_at: str
    valid_from: str | None
    valid_to: str | None
    recorded_at: str
    superseded_at: str | None
    knowledge_cutoff: str


class SnapshotDerivation(TypedDict):
    """A typed parent -> child edge between two snapshots.

    Keys:
        parent_snapshot_id: The snapshot the child was derived from.
        child_snapshot_id: The derived snapshot.
        derivation_kind: One of :data:`DerivationKind`.
        derived_at: When the derivation happened.
        tool_reference: The tool / commit that produced it.
    """

    parent_snapshot_id: str
    child_snapshot_id: str
    derivation_kind: DerivationKind
    derived_at: str
    tool_reference: str


class SnapshotPromotion(TypedDict):
    """One immutable promotion-history row for a (target, environment).

    Changing the approved baseline appends a new row and closes the prior
    row's ``valid_to``; it never rewrites a row.

    Keys:
        promotion_id: Stable id of this promotion record.
        target_reference: What is being promoted for (a release, an env, ...).
        environment: One of :data:`PromotionEnvironment`.
        snapshot_id: The promoted snapshot.
        state: One of :data:`PromotionState`.
        version: Optimistic-concurrency counter for the (target, environment).
        valid_from: Start of this record's effective interval.
        valid_to: End of the interval (None = currently effective).
        recorded_at: When pg-erd-cloud recorded this row.
        actor: Who promoted / superseded / rejected.
        reason: Free-text justification.
    """

    promotion_id: str
    target_reference: str
    environment: PromotionEnvironment
    snapshot_id: str
    state: PromotionState
    version: int
    valid_from: str
    valid_to: str | None
    recorded_at: str
    actor: str
    reason: str


class RetentionPolicy(TypedDict):
    """A declared retention rule (a policy record, not an action).

    Keys:
        policy_id: Stable id.
        scope_reference: What the policy applies to.
        retain_days: Keep for at least this many days after ``available_at``.
        archive_after_days: Eligible for archive after this many days.
        delete_after_days: Eligible for deletion after this many days.
        applies_to_promoted: Whether promoted baselines are in scope.
    """

    policy_id: str
    scope_reference: str
    retain_days: int
    archive_after_days: int | None
    delete_after_days: int | None
    applies_to_promoted: bool


class RecoveryCheckpoint(TypedDict):
    """A restorable product-metadata + diagram state (never a live DB state).

    Keys:
        checkpoint_id: Stable id.
        snapshot_id: The snapshot whose metadata this checkpoint restores.
        diagram_view_reference: The saved diagram state to restore, if any.
        created_at: When the checkpoint was taken.
        note: Free-text description.
    """

    checkpoint_id: str
    snapshot_id: str
    diagram_view_reference: str | None
    created_at: str
    note: str


class AuditEventRecord(TypedDict):
    """One append-only audit fact about a lifecycle change.

    Keys:
        event_id: Stable id.
        occurred_at: When it happened.
        actor: Who did it.
        action: What happened (e.g. ``promotion.recorded``).
        subject_reference: What it was about (a snapshot / promotion id).
        detail: Non-sensitive structured context as a JSON string.
    """

    event_id: str
    occurred_at: str
    actor: str
    action: str
    subject_reference: str
    detail: str
