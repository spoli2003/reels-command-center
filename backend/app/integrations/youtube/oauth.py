import json
import os
from pathlib import Path
from typing import Any

from app.core.config import Settings

# youtube.force-ssl is a superset of youtube.readonly (read) that also grants
# write access (posting/editing/deleting comments) — required for Release 0.7.0's
# Community Inbox. There is no narrower official scope that permits posting
# replies, so this is the least-privilege scope that accomplishes the goal (see
# docs/DECISIONS.md ADR-017). Existing connections must re-consent to this scope
# — see YoutubeStatus.comments_scope_granted / the reconnect flow in api/youtube.py.
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

COMMENTS_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl"


def has_comments_scope(granted_scopes: str) -> bool:
    return COMMENTS_SCOPE in (granted_scopes or "").split()


def load_client_secrets(path: Path) -> dict:
    """Shared by the manual /sync endpoint and the automatic scheduler so both
    build OAuth credentials the exact same way."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("web") or data.get("installed") or {}


def configure_local_oauth(settings: Settings) -> None:
    if settings.environment == "development" and settings.oauth_insecure_transport:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"


def build_flow(
    settings: Settings,
    state: str | None = None,
    code_verifier: str | None = None,
) -> Any:
    from google_auth_oauthlib.flow import Flow

    configure_local_oauth(settings)
    path = Path(settings.google_client_secrets_file)
    if not path.exists():
        raise FileNotFoundError(f"Brak pliku OAuth: {path}")
    flow = Flow.from_client_secrets_file(
        str(path),
        scopes=SCOPES,
        state=state,
        code_verifier=code_verifier,
        autogenerate_code_verifier=code_verifier is None,
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow
