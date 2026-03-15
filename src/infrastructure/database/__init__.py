"""Database infrastructure module."""

from src.infrastructure.database import schema
from src.infrastructure.database.connection import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseInitializationError,
    get_db,
    get_db_path,
    init_database,
)

__all__ = [
    "get_db",
    "init_database",
    "get_db_path",
    "schema",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseInitializationError",
]
