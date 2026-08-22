from __future__ import annotations

from sqlalchemy.orm import Session

from pokequant.db.models import AuditEvent


def audit(
    session: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | int,
    details: str = "",
    actor: str = "system",
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details,
    )
    session.add(event)
    return event
