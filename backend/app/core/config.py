from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Reels Command Center API"
    environment: str = "development"
    database_url: str = "sqlite:///./rcc.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    session_secret: str = "change-me-in-env"
    jwt_secret: str = "change-me-jwt-secret"
    access_token_minutes: int = 10080
    redis_url: str = "redis://redis:6379/0"
    token_encryption_key: str = ""
    google_client_secrets_file: str = "secrets/google_client_secret.json"
    google_redirect_uri: str = "http://127.0.0.1:8000/api/integrations/youtube/callback"
    frontend_url: str = "http://127.0.0.1:3000"
    oauth_insecure_transport: bool = True
    # Automatic sync scheduler (Sprint 6 / Part 5) — disabled by default per
    # docs/DECISIONS.md ADR-009; must be explicitly opted into via env var.
    youtube_sync_enabled: bool = False
    youtube_sync_interval_hours: float = 6.0
    # Meta (Facebook + Instagram) OAuth — Release 0.8.0 / ADR-021. The user must
    # create a Meta Developer App and provide these; RCC cannot create one on
    # their behalf (same bootstrap step YouTube required with
    # google_client_secret.json).
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/platforms/meta/callback"
    meta_graph_api_version: str = "v19.0"
    # Facebook Login for Business Configuration ID (optional). Some app types no
    # longer expose the classic scope-based Login product at all — only
    # Configurations, each pre-defining its own permission set. When set, the
    # authorize URL sends config_id instead of scope (Meta ignores/rejects a
    # redundant scope alongside config_id); when empty, the classic scope-based
    # flow (SCOPES in app/integrations/meta/oauth.py) is used unchanged.
    meta_login_config_id: str = ""
    # Automatic Facebook/Instagram sync. Mirrors the opt-in YouTube scheduler:
    # one in-process task, disabled unless the operator explicitly enables it.
    meta_sync_enabled: bool = False
    meta_sync_interval_hours: float = 6.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def client_secrets_path(self) -> Path:
        return Path(self.google_client_secrets_file)


@lru_cache
def get_settings() -> Settings:
    return Settings()
