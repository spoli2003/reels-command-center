import json
import os
from pathlib import Path
from typing import Any

from app.core.config import Settings

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


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
