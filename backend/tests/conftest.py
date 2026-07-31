import os

_TEST_DB_PATH = "./test-rcc.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-secret"
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("GOOGLE_CLIENT_SECRETS_FILE", "tests/fixtures/google_client_secret.json")

if os.path.exists(_TEST_DB_PATH):
    os.remove(_TEST_DB_PATH)

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine

Base.metadata.create_all(bind=engine)
