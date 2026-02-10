from __future__ import annotations

from typing import Any

from apps.data.models import AuditEvent


def log_audit_event(
    *,
    actor=None,
    event_type: str,
    target_type: str = "",
    target_id: Any = "",
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Best-effort audit logging that never breaks the caller flow."""
    try:
        AuditEvent.objects.create(
            actor=actor if getattr(actor, "is_authenticated", False) else None,
            event_type=event_type or "other",
            target_type=str(target_type or ""),
            target_id=str(target_id or ""),
            before_json=before or {},
            after_json=after or {},
            metadata_json=metadata or {},
        )
    except Exception:
        # Audit logging should not block business action.
        return

