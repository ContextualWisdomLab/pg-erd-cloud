"""Snapshot lineage, promotion, retention, and recovery model (issue #948).

A timestamped list of snapshots is not a lifecycle. This package adds the
normalized lifecycle facts a buyer needs -- which snapshot was the approved
baseline for a release/environment, who promoted or superseded it and why,
what was derived from it, and what is retained / archived / legally held /
deletable -- as **pure model + algorithms**. Persistence (Alembic tables,
repositories, HTTP surface) is a later increment; nothing here touches the
database.

Key principle: **capture time is not valid time.** A snapshot captured later
may describe an earlier database state, so the lineage record keeps
``captured_at`` / ``available_at`` / ``valid_from`` / ``valid_to`` /
``recorded_at`` / ``superseded_at`` / ``knowledge_cutoff`` as separate facts.

"Recover snapshot/view" restores product metadata and a selected diagram state
only -- live customer-database recovery is a separate, separately-approved
workflow and is never implied here.
"""

from app.lineage.derive import (
    DERIVATION_KINDS,
    LineageCycleError,
    build_lineage_graph,
)
from app.lineage.lineage_model import (
    AuditEventRecord,
    PromotionEnvironment,
    PromotionState,
    RecoveryCheckpoint,
    RetentionDisposition,
    RetentionPolicy,
    SnapshotDerivation,
    SnapshotLineage,
    SnapshotPromotion,
)
from app.lineage.promote import PromotionConflictError, apply_promotion
from app.lineage.retention import decide_retention

__all__ = [
    "DERIVATION_KINDS",
    "AuditEventRecord",
    "LineageCycleError",
    "PromotionConflictError",
    "PromotionEnvironment",
    "PromotionState",
    "RecoveryCheckpoint",
    "RetentionDisposition",
    "RetentionPolicy",
    "SnapshotDerivation",
    "SnapshotLineage",
    "SnapshotPromotion",
    "apply_promotion",
    "build_lineage_graph",
    "decide_retention",
]
