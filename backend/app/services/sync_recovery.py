"""Recover sync runs orphaned by a backend restart.

A row marked ``running`` belongs to the process that created it. During local
development Uvicorn reloads whenever source files change; that process exits
without reaching the normal failure handler and leaves the row behind. At the
next application startup no old run can still be active, so it is safe to mark
all such rows as interrupted before schedulers or manual syncs start.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import SyncRun


INTERRUPTED_MESSAGE = "Przerwana przez restart backendu podczas synchronizacji."


def recover_interrupted_sync_runs(db: Session) -> int:
    runs = list(db.scalars(select(SyncRun).where(SyncRun.status == "running")).all())
    if not runs:
        return 0

    finished_at = datetime.now(timezone.utc)
    for run in runs:
        run.status = "failed"
        run.error_message = INTERRUPTED_MESSAGE
        run.finished_at = finished_at
    db.commit()
    return len(runs)
