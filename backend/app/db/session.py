from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

if settings.database_url.startswith("sqlite"):
    # Standard SQLAlchemy workaround: pysqlite's own transaction handling conflicts
    # with SAVEPOINT (session.begin_nested()), which the sync engine relies on for
    # per-video fault isolation (app/services/youtube_sync.py). Without this, a
    # single bad video's API response could roll back an entire sync run's data.
    @event.listens_for(engine, "connect")
    def _sqlite_disable_pysqlite_transactions(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _sqlite_emit_begin(conn):
        conn.exec_driver_sql("BEGIN")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
