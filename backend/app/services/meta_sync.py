"""One orchestration path for manual, initial and scheduled Meta syncs.

Content and comments deliberately keep their own SyncRun rows because they
have different counters and overlap guards. This service only coordinates the
two existing generic engines so every trigger performs the same work.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.meta.client import GraphClient
from app.integrations.meta.oauth import INSTAGRAM_INSIGHTS_SCOPES
from app.models.integration import PlatformAccount, SyncRun
from app.services.content_comment_sync import ContentCommentSyncAlreadyRunningError, sync_platform_comments
from app.services.content_sync import sync_platform_content
from app.services.platforms.base import PlatformAdapter
from app.services.platforms.facebook_adapter import FacebookAdapter
from app.services.platforms.instagram_adapter import InstagramAdapter
from app.services.token_crypto import decrypt_token


@dataclass
class MetaSyncResult:
    content_run: SyncRun
    comment_run: Optional[SyncRun]
    comment_error: Optional[str] = None

    @property
    def status(self) -> str:
        statuses = [self.content_run.status]
        if self.comment_run is not None:
            statuses.append(self.comment_run.status)
        if self.comment_error or "failed" in statuses:
            return "partial"
        return "partial" if "partial" in statuses else "success"


def build_meta_adapter(account: PlatformAccount, settings: Settings) -> PlatformAdapter:
    token = decrypt_token(account.access_token_encrypted, settings.token_encryption_key)
    client = GraphClient(token, settings.meta_graph_api_version)
    if account.platform == "facebook":
        return FacebookAdapter(client, account.external_account_id)
    if account.platform == "instagram":
        granted_scopes = {scope for scope in account.scopes.split(",") if scope}
        return InstagramAdapter(
            client,
            account.external_account_id,
            own_username=account.display_name,
            include_insights=INSTAGRAM_INSIGHTS_SCOPES <= granted_scopes,
        )
    raise ValueError(f"Platforma '{account.platform}' nie jest kontem Meta.")


def sync_meta_account(
    db: Session,
    account: PlatformAccount,
    settings: Settings,
    *,
    sync_comments: bool = True,
    comment_skip_reason: Optional[str] = None,
) -> MetaSyncResult:
    """Synchronize content first, then comments for the imported publications.

    A comment-side API failure is reported as a partial result without undoing
    a successful content sync. Programming errors still propagate; the narrow
    overlap case is the only expected exception handled here.
    """
    adapter = build_meta_adapter(account, settings)
    get_audience_count = getattr(adapter, "get_audience_count", None)
    if get_audience_count is not None:
        try:
            audience_count = get_audience_count()
        except Exception:
            # Account-level audience is an optional enrichment. A temporary
            # denial must never block content/comment synchronization.
            audience_count = None
        if audience_count is not None:
            account.audience_count = audience_count
            db.commit()
    content_run = sync_platform_content(db, account, adapter)
    if not sync_comments:
        return MetaSyncResult(
            content_run=content_run,
            comment_run=None,
            comment_error=comment_skip_reason or "Synchronizacja komentarzy jest niedostępna dla tego połączenia.",
        )
    try:
        comment_run = sync_platform_comments(db, account, adapter)
    except ContentCommentSyncAlreadyRunningError as exc:
        return MetaSyncResult(content_run=content_run, comment_run=None, comment_error=str(exc))
    return MetaSyncResult(content_run=content_run, comment_run=comment_run)
