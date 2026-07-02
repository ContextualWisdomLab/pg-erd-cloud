from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BillingEvent
from app.schemas import BillingEntitlementOut
from app.settings import settings

_ENTITLEMENT_SEAT_METADATA_KEYS = (
    "seat_count",
    "seats",
    "seat_limit",
    "licensed_seats",
    "quantity",
)


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _positive_int_metadata_value(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _entitlement_seat_count(metadata: object) -> int | None:
    if not isinstance(metadata, Mapping):
        return None
    for key in _ENTITLEMENT_SEAT_METADATA_KEYS:
        if key in metadata:
            parsed = _positive_int_metadata_value(metadata[key])
            if parsed is not None:
                return parsed
    return None


def empty_billing_entitlement() -> BillingEntitlementOut:
    return BillingEntitlementOut(
        plan=None,
        seat_count=None,
        source_provider=None,
        source_provider_event_id=None,
        source_event_type=None,
        source_occurred_at=None,
    )


def billing_entitlement_from_events(
    events: list[BillingEvent],
) -> BillingEntitlementOut:
    entitlement_event_types = _split_csv(settings.billing_entitlement_event_types)
    if not entitlement_event_types:
        return empty_billing_entitlement()

    for event in sorted(
        events,
        key=lambda item: (item.occurred_at, item.received_at),
        reverse=True,
    ):
        if event.event_type not in entitlement_event_types or not event.target_plan:
            continue
        return BillingEntitlementOut(
            plan=event.target_plan,
            seat_count=_entitlement_seat_count(event.metadata_json),
            source_provider=event.provider,
            source_provider_event_id=event.provider_event_id,
            source_event_type=event.event_type,
            source_occurred_at=event.occurred_at,
        )

    return empty_billing_entitlement()


async def latest_billing_entitlement_for_subject(
    session: AsyncSession,
    subject: str,
) -> BillingEntitlementOut:
    result = await session.execute(
        select(BillingEvent)
        .where(BillingEvent.subject == subject)
        .order_by(desc(BillingEvent.received_at))
        .limit(10)
    )
    return billing_entitlement_from_events(list(result.scalars().all()))
