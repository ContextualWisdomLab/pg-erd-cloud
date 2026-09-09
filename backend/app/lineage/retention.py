"""Decide a retention disposition -- a record, never a delete.

Pure: no I/O. :func:`decide_retention` returns one of
:data:`~app.lineage.lineage_model.RetentionDisposition` for a snapshot given a
policy and the current time. It never removes anything; disposition is
evidence a human or a separate, audited job acts on.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _parse(ts: str) -> dt.datetime:
    """Parse an ISO-8601 timestamp, treating a bare value as UTC."""

    value = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value


def decide_retention(
    policy: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    now: dt.datetime,
    under_legal_hold: bool = False,
    is_promoted: bool = False,
) -> dict[str, Any]:
    """Return a retention-disposition record for one snapshot.

    Args:
        policy: A ``RetentionPolicy``-shaped dict (``retain_days``,
            ``archive_after_days``, ``delete_after_days``,
            ``applies_to_promoted``).
        snapshot: A ``SnapshotLineage``-shaped dict; ``available_at`` anchors
            the age calculation.
        now: The current time (timezone-aware).
        under_legal_hold: If true, the disposition is always ``legal_hold``.
        is_promoted: Whether this snapshot is a promoted baseline. A promoted
            baseline is never ``delete_eligible`` unless the policy opts in via
            ``applies_to_promoted``.

    Returns:
        ``{"snapshot_id", "policy_id", "disposition", "age_days", "decided_at"}``.
        ``disposition`` is one of ``retain`` / ``archive_eligible`` /
        ``delete_eligible`` / ``legal_hold``. No deletion is performed.
    """

    available_at = _parse(str(snapshot["available_at"]))
    age_days = (now - available_at).days

    if under_legal_hold:
        disposition = "legal_hold"
    else:
        retain_days = int(policy["retain_days"])
        archive_after = policy.get("archive_after_days")
        delete_after = policy.get("delete_after_days")
        may_delete_promoted = bool(policy.get("applies_to_promoted", False))

        disposition = "retain"
        if archive_after is not None and age_days >= int(archive_after):
            disposition = "archive_eligible"
        if (
            delete_after is not None
            and age_days >= int(delete_after)
            and age_days >= retain_days
            and (not is_promoted or may_delete_promoted)
        ):
            disposition = "delete_eligible"

    return {
        "snapshot_id": snapshot["snapshot_id"],
        "policy_id": policy["policy_id"],
        "disposition": disposition,
        "age_days": age_days,
        "decided_at": now.isoformat(),
    }
