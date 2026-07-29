"""The one place that turns a stored PlatformAccount's encrypted tokens into a
usable YoutubeClient. Previously duplicated between the manual /sync endpoint and
the automatic scheduler; consolidated here for Release 0.7.0 so the new comment
sync/reply endpoints don't introduce a third copy (see docs/DECISIONS.md ADR-016
for the "one source of truth" precedent this follows)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.youtube.client import YoutubeClient, credentials_from_tokens
from app.integrations.youtube.oauth import load_client_secrets
from app.models.integration import PlatformAccount, YoutubeChannel
from app.services.token_crypto import decrypt_token


class NotConnectedError(Exception):
    """Raised when an endpoint needs a connected YouTube account and there isn't one."""


def get_connected_account_and_channel(db: Session) -> tuple[PlatformAccount, YoutubeChannel]:
    account = db.scalar(select(PlatformAccount).where(PlatformAccount.platform == "youtube"))
    if account is None:
        raise NotConnectedError("Najpierw połącz konto YouTube")
    channel = db.scalar(select(YoutubeChannel).where(YoutubeChannel.account_id == account.id))
    if channel is None:
        raise NotConnectedError("Konto połączone, ale brak zsynchronizowanego kanału — uruchom pierwszą synchronizację")
    return account, channel


def build_youtube_client(account: PlatformAccount, settings: Settings) -> YoutubeClient:
    data = load_client_secrets(settings.client_secrets_path)
    credentials = credentials_from_tokens(
        decrypt_token(account.access_token_encrypted, settings.token_encryption_key),
        decrypt_token(account.refresh_token_encrypted, settings.token_encryption_key) if account.refresh_token_encrypted else None,
        data["client_id"],
        data["client_secret"],
        data.get("token_uri", "https://oauth2.googleapis.com/token"),
    )
    return YoutubeClient(credentials)
