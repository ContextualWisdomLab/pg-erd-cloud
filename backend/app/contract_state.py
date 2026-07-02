from __future__ import annotations

from typing import Literal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BillingEvent
from app.settings import settings

ContractState = Literal["active", "deactivated"]


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def contract_state_event_types() -> set[str]:
    return _split_csv(settings.billing_contract_active_event_types) | _split_csv(
        settings.billing_contract_deactivated_event_types
    )


def contract_state_for_event_type(event_type: str) -> ContractState | None:
    if event_type in _split_csv(settings.billing_contract_deactivated_event_types):
        return "deactivated"
    if event_type in _split_csv(settings.billing_contract_active_event_types):
        return "active"
    return None


async def latest_contract_state_for_subject(
    session: AsyncSession,
    subject: str,
) -> ContractState | None:
    if not settings.billing_contract_state_events_enabled:
        return None

    event_types = contract_state_event_types()
    if not event_types:
        return None

    result = await session.execute(
        select(BillingEvent)
        .where(
            BillingEvent.subject == subject,
            BillingEvent.event_type.in_(event_types),
        )
        .order_by(desc(BillingEvent.occurred_at), desc(BillingEvent.received_at))
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if event is None:
        return None
    return contract_state_for_event_type(event.event_type)
