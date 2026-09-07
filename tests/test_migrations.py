from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings


def test_migrations_build_clean_database(tmp_path: Path, monkeypatch):
    database_path = tmp_path / "migration-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    tables = set(inspect(create_engine(f"sqlite:///{database_path.as_posix()}")).get_table_names())
    assert {"products", "truth_versions", "operator_sessions", "audit_events"} <= tables
    command.downgrade(config, "base")
    get_settings.cache_clear()
