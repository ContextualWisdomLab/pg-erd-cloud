from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics import record_llm_draft_metrics
from app.models import LlmDraftUsageEvent, utcnow

_LOGGER = logging.getLogger("app.llm_usage")


def _snapshot_input_chars(snapshot_json: dict[str, Any]) -> int:
    try:
        return len(
            json.dumps(
                snapshot_json,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError):
        return len(str(snapshot_json))


def record_llm_draft_usage(
    *,
    surface: str,
    artifact: str,
    outcome: str,
    snapshot_json: dict[str, Any],
    output_text: str | None = None,
    user_account_uuid: uuid.UUID | None = None,
    project_space_uuid: uuid.UUID | None = None,
    schema_snapshot_uuid: uuid.UUID | None = None,
    share_link_uuid: uuid.UUID | None = None,
    error_code: str | None = None,
) -> dict[str, object | None]:
    """Record LLM draft cost/usage evidence without logging prompt contents."""
    input_chars = _snapshot_input_chars(snapshot_json)
    output_chars = len(output_text) if output_text is not None else None
    record_llm_draft_metrics(
        surface=surface,
        artifact=artifact,
        outcome=outcome,
        input_chars=input_chars,
        output_chars=output_chars,
    )
    payload: dict[str, object | None] = {
        "event": "llm_draft_usage",
        "surface": surface,
        "artifact": artifact,
        "outcome": outcome,
        "input_chars": input_chars,
        "output_chars": output_chars,
        "user_account_uuid": str(user_account_uuid) if user_account_uuid else None,
        "project_space_uuid": str(project_space_uuid) if project_space_uuid else None,
        "schema_snapshot_uuid": (
            str(schema_snapshot_uuid) if schema_snapshot_uuid else None
        ),
        "share_link_uuid": str(share_link_uuid) if share_link_uuid else None,
        "error_code": error_code,
    }
    _LOGGER.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return payload


async def record_persistent_llm_draft_usage(
    session: AsyncSession,
    *,
    surface: str,
    artifact: str,
    outcome: str,
    snapshot_json: dict[str, Any],
    output_text: str | None = None,
    subject: str | None = None,
    user_account_uuid: uuid.UUID | None = None,
    project_space_uuid: uuid.UUID | None = None,
    schema_snapshot_uuid: uuid.UUID | None = None,
    share_link_uuid: uuid.UUID | None = None,
    error_code: str | None = None,
) -> LlmDraftUsageEvent:
    """Record metrics/logs and persist monthly billing attribution evidence."""
    input_chars = _snapshot_input_chars(snapshot_json)
    output_chars = len(output_text) if output_text is not None else None
    record_llm_draft_usage(
        surface=surface,
        artifact=artifact,
        outcome=outcome,
        snapshot_json=snapshot_json,
        output_text=output_text,
        user_account_uuid=user_account_uuid,
        project_space_uuid=project_space_uuid,
        schema_snapshot_uuid=schema_snapshot_uuid,
        share_link_uuid=share_link_uuid,
        error_code=error_code,
    )
    event = LlmDraftUsageEvent(
        llm_draft_usage_event_uuid=uuid.uuid4(),
        surface=surface,
        artifact=artifact,
        outcome=outcome,
        subject=subject,
        user_account_uuid=user_account_uuid,
        project_space_uuid=project_space_uuid,
        schema_snapshot_uuid=schema_snapshot_uuid,
        share_link_uuid=share_link_uuid,
        input_chars=input_chars,
        output_chars=output_chars,
        error_code=error_code,
        occurred_at=utcnow(),
    )
    session.add(event)
    await session.commit()
    return event
