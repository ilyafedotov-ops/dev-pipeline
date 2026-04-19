from pathlib import Path

import pytest

from devgodzilla.config import Config, load_config
from devgodzilla.db.database import PostgresDatabase, SQLiteDatabase
from devgodzilla.db.database import get_database


def test_protocol_helper_methods_exist_on_both_database_backends() -> None:
    helper_methods = [
        "update_protocol_paths",
        "update_protocol_windmill",
        "update_protocol_template",
        "update_protocol_policy_audit",
    ]

    for cls in (SQLiteDatabase, PostgresDatabase):
        for method_name in helper_methods:
            assert callable(getattr(cls, method_name, None)), f"{cls.__name__}.{method_name} is missing"


def test_config_requires_exactly_one_database_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one database backend"):
        Config(
            db_url="postgresql://devgodzilla:changeme@localhost:5432/devgodzilla_db",
            db_path=tmp_path / "devgodzilla.sqlite",
        )


def test_load_config_requires_database_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVGODZILLA_DB_URL", "")
    monkeypatch.setenv("DEVGODZILLA_DB_PATH", "")

    with pytest.raises(ValueError, match="Database is not configured"):
        load_config()


def test_get_database_requires_single_explicit_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one database backend"):
        get_database(
            db_url="postgresql://devgodzilla:changeme@localhost:5432/devgodzilla_db",
            db_path=tmp_path / "devgodzilla.sqlite",
        )

    with pytest.raises(ValueError, match="Database is not configured"):
        get_database()
