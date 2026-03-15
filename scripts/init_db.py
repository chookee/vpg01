#!/usr/bin/env python3
"""Database initialization script.

Creates SQLite database file and initializes schema with all tables and indexes.
"""

import logging
import sqlite3
import sys
import traceback
from pathlib import Path

# Configure basic logging for script output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Initialize database.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Добавляем корень проекта в sys.path для импорта из src
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.infrastructure.database.connection import get_db_path
        from src.infrastructure.database.schema import (
            CREATE_INDEXES,
            CREATE_MESSAGES_TABLE,
            CREATE_SESSIONS_TABLE,
            CREATE_USERS_TABLE,
        )

        db_path = get_db_path()
        db_dir = Path(db_path).parent

        # Validate and create directory
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            except OSError as e:
                logger.error(f"Failed to create database directory {db_dir}: {e}")
                return 1

        # Check if database already exists
        db_exists = Path(db_path).exists()
        if db_exists:
            logger.warning(f"Database file already exists: {db_path}")
            logger.info("Skipping initialization to prevent data loss.")
            return 0

        logger.info(f"Initializing database: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            # Enable foreign keys
            cursor.execute("PRAGMA foreign_keys = ON;")

            # Create tables in a single transaction
            cursor.executescript(f"""
                BEGIN TRANSACTION;
                {CREATE_USERS_TABLE}
                {CREATE_SESSIONS_TABLE}
                {CREATE_MESSAGES_TABLE}
                {CREATE_INDEXES}
                COMMIT;
            """)

            conn.commit()
            logger.info("Database initialized successfully.")
            return 0

        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"SQLite error during initialization: {e}")
            return 1
        finally:
            conn.close()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.debug(traceback.format_exc())
        return 1
    except KeyboardInterrupt:
        logger.info("Initialization interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
