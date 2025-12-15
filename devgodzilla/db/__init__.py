"""
DevGodzilla Database Package

Database layer with dual SQLite and PostgreSQL support.
"""

from devgodzilla.db.database import (
    Database,
    DatabaseProtocol,
    SQLiteDatabase,
    PostgresDatabase,
    get_database,
)
from devgodzilla.db.schema import SCHEMA_SQLITE, SCHEMA_POSTGRES

__all__ = [
    "Database",
    "DatabaseProtocol",
    "SQLiteDatabase",
    "PostgresDatabase",
    "get_database",
    "SCHEMA_SQLITE",
    "SCHEMA_POSTGRES",
]
