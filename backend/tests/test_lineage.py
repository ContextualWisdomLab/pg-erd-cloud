"""Tests for the ``app.lineage`` model + algorithms (issue #948)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.lineage import (
    LineageCycleError,
    PromotionConflictError,
    apply_promotion,
    build_lineage_graph,
    decide_retention,
)


def _edge(parent: str, child: str, kind: str) -> dict[str, object]:
    return {
        "parent_snapshot_id": parent,
        "child_snapshot_id": child,
        "derivation_kind": kind,
        "derived_at": "2026-01-01T00:00:00+00:00",
        "tool_reference": "tool@abc123",
    }


def test_graph_keeps_edges_by_kind_and_gives_a_topological_order() -> None:
    graph = build_lineage_graph(
        ["s1", "s2", "s3", "s4"],
        [
            _edge("s1", "s2", "captured_from"),
            _edge("s2", "s3", "normalized_from"),
            _edge("s2", "s4", "exported_from"),
        ],
    )
    assert graph["edges_by_kind"] == {
        "captured_from": [["s1", "s2"]],
        "exported_from": [["s2", "s4"]],
        "normalized_from": [["s2", "s3"]],
    }
    order = graph["topological_order"]
    assert order.index("s1") < order.index("s2") < order.index("s3")
    assert order.index("s2") < order.index("s4")
    assert graph["roots"] == ["s1"]
    assert graph["leaves"] == ["s3", "s4"]


def test_unknown_edge_kind_and_self_loop_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown derivation_kind"):
        build_lineage_graph(["a", "b"], [_edge("a", "b", "derived_from")])
    with pytest.raises(ValueError, match="self-loop"):
        build_lineage_graph(["a"], [_edge("a", "a", "compared_with")])


def test_cycle_is_rejected_with_the_involved_ids() -> None:
    with pytest.raises(LineageCycleError) as exc:
        build_lineage_graph(
            ["a", "b", "c"],
            [
                _edge("a", "b", "normalized_from"),
                _edge("b", "c", "normalized_from"),
                _edge("c", "a", "compared_with"),
            ],
        )
    assert exc.value.involved == ["a", "b", "c"]


def test_orphans_and_dangling_references_are_reported_not_errors() -> None:
    graph = build_lineage_graph(
        ["lonely", "p", "c"],
        [_edge("p", "c", "captured_from"), _edge("p", "ghost", "exported_from")],
    )
    assert graph["orphans"] == ["lonely"]
    assert graph["dangling_references"] == ["ghost"]
    assert "ghost" in graph["nodes"]


def _promo(pid: str, snap: str, version: int, valid_from: str, valid_to: str | None) -> dict[str, object]:
    return {
        "promotion_id": pid,
        "target_reference": "release_2026_09",
        "environment": "production",
        "snapshot_id": snap,
        "state": "promoted",
        "version": version,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recorded_at": valid_from,
        "actor": "release-manager",
        "reason": "baseline",
    }


def _request(pid: str, snap: str, expected_version: int, valid_from: str) -> dict[str, object]:
    return {
        "promotion_id": pid,
        "target_reference": "release_2026_09",
        "environment": "production",
        "snapshot_id": snap,
        "valid_from": valid_from,
        "recorded_at": valid_from,
        "actor": "release-manager",
        "reason": "promote newer baseline",
        "expected_version": expected_version,
    }


def test_first_promotion_and_supersession_closes_the_prior_interval() -> None:
    history = apply_promotion([], _request("p1", "s1", 0, "2026-09-01T00:00:00+00:00"))
    assert len(history) == 1
    assert history[0]["version"] == 1 and history[0]["valid_to"] is None

    history = apply_promotion(history, _request("p2", "s2", 1, "2026-09-10T00:00:00+00:00"))
    assert len(history) == 2
    # Prior row's interval is closed, not rewritten.
    assert history[0]["snapshot_id"] == "s1"
    assert history[0]["valid_to"] == "2026-09-10T00:00:00+00:00"
    assert history[0]["superseded_at"] == "2026-09-10T00:00:00+00:00"
    assert history[1]["snapshot_id"] == "s2" and history[1]["valid_to"] is None
    assert history[1]["version"] == 2


def test_stale_expected_version_is_a_conflict() -> None:
    history = apply_promotion([], _request("p1", "s1", 0, "2026-09-01T00:00:00+00:00"))
    with pytest.raises(PromotionConflictError) as exc:
        apply_promotion(history, _request("p2", "s2", 0, "2026-09-05T00:00:00+00:00"))
    assert exc.value.expected == 0 and exc.value.actual == 1


def test_promotion_targeting_a_different_environment_is_rejected() -> None:
    history = apply_promotion([], _request("p1", "s1", 0, "2026-09-01T00:00:00+00:00"))
    bad = _request("p2", "s2", 1, "2026-09-05T00:00:00+00:00")
    bad["environment"] = "staging"
    with pytest.raises(ValueError, match="different"):
        apply_promotion(history, bad)


def test_retention_decision_is_a_record_and_never_deletes() -> None:
    policy = {
        "policy_id": "pol_default",
        "scope_reference": "all_snapshots",
        "retain_days": 30,
        "archive_after_days": 90,
        "delete_after_days": 365,
        "applies_to_promoted": False,
    }
    snap = {"snapshot_id": "s1", "available_at": "2026-01-01T00:00:00+00:00"}
    now = dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc)  # ~120 days old
    decision = decide_retention(policy, snap, now=now)
    assert decision["disposition"] == "archive_eligible"
    assert decision["age_days"] == 120
    assert set(decision) == {"snapshot_id", "policy_id", "disposition", "age_days", "decided_at"}

    old = dt.datetime(2027, 6, 1, tzinfo=dt.timezone.utc)  # > 365 days
    assert decide_retention(policy, snap, now=old)["disposition"] == "delete_eligible"
    # A promoted baseline is protected from delete unless the policy opts in.
    assert decide_retention(policy, snap, now=old, is_promoted=True)["disposition"] == "archive_eligible"
    # Legal hold always wins.
    assert decide_retention(policy, snap, now=old, under_legal_hold=True)["disposition"] == "legal_hold"
