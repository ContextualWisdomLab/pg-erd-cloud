"""Append-only promotion with optimistic concurrency.

Pure: no I/O. Promoting a new baseline for a ``(target_reference,
environment)`` **closes the prior effective interval** and appends a new row;
it never rewrites history. A stale ``expected_version`` is rejected so two
concurrent promoters cannot both "win".
"""

from __future__ import annotations

from typing import Any


class PromotionConflictError(RuntimeError):
    """Raised when a promotion request's ``expected_version`` is stale."""

    def __init__(self, expected: int, actual: int) -> None:
        """Record the version the caller expected and the version found."""

        self.expected = expected
        self.actual = actual
        super().__init__(
            f"promotion rejected: expected version {expected}, "
            f"current version is {actual}"
        )


def _effective_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the currently effective promotion row (``valid_to is None``)."""

    effective = [r for r in rows if r.get("valid_to") is None and r.get("state") == "promoted"]
    return effective[-1] if effective else None


def apply_promotion(
    current_promotions: list[dict[str, Any]],
    request: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the new promotion history after applying ``request``.

    Args:
        current_promotions: The existing promotion rows for one
            ``(target_reference, environment)``, oldest first. Each is a
            ``SnapshotPromotion``-shaped dict.
        request: A dict with ``promotion_id``, ``target_reference``,
            ``environment``, ``snapshot_id``, ``valid_from``, ``recorded_at``,
            ``actor``, ``reason``, ``expected_version`` (the version the caller
            last saw; ``0`` for a first promotion), and optional ``state``
            (default ``"promoted"``; ``"rejected"`` records a rejection without
            closing the effective interval).

    Returns:
        A **new** list: the input rows (with the previously effective row's
        ``valid_to`` set to ``request["valid_from"]`` when the new state is
        ``"promoted"``) followed by the new row with ``valid_to = None`` and
        ``version`` incremented.

    Raises:
        ValueError: If the request targets a different (target, environment)
            than the existing rows, or ``valid_from`` precedes the effective
            row's ``valid_from``.
        PromotionConflictError: If ``expected_version`` != the current version.
    """

    rows = [dict(r) for r in current_promotions]
    current_version = max((int(r["version"]) for r in rows), default=0)
    expected = int(request["expected_version"])
    if expected != current_version:
        raise PromotionConflictError(expected, current_version)

    if rows:
        first = rows[0]
        if (first["target_reference"], first["environment"]) != (
            request["target_reference"],
            request["environment"],
        ):
            raise ValueError("request targets a different (target, environment)")

    state = str(request.get("state", "promoted"))
    effective = _effective_row(rows)
    if state == "promoted" and effective is not None:
        if request["valid_from"] < effective["valid_from"]:
            raise ValueError(
                "valid_from precedes the currently effective interval start"
            )
        effective["valid_to"] = request["valid_from"]
        effective["superseded_at"] = request.get("recorded_at")

    new_row: dict[str, Any] = {
        "promotion_id": request["promotion_id"],
        "target_reference": request["target_reference"],
        "environment": request["environment"],
        "snapshot_id": request["snapshot_id"],
        "state": state,
        "version": current_version + 1,
        "valid_from": request["valid_from"],
        "valid_to": None,
        "recorded_at": request["recorded_at"],
        "actor": request["actor"],
        "reason": request["reason"],
    }
    rows.append(new_row)
    return rows
