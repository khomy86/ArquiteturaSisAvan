from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from . import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

# Any constant works, as long as nothing else in the database uses the same key.
_MIGRATION_LOCK_ID = 0x75A1F11C


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations(after=None) -> None:
    """Bring the schema up to date, then call `after(session)` if given.

    Both catalog instances do this on startup. The advisory lock makes the
    second one wait until the first has committed, and it then finds nothing
    left to do.
    """
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))

    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": _MIGRATION_LOCK_ID})
        alembic_cfg.attributes["connection"] = conn
        command.upgrade(alembic_cfg, "head")
        if after is not None:
            with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
                after(session)
