#!/usr/bin/env python3
"""Test script for desktop session initialization.

This script tests the DesktopSessionManager by creating or retrieving
a session for the desktop application.

Usage:
    python scripts/test_desktop_session.py

Example output:
    Testing desktop session initialization...
    [OK] Desktop session initialized: session_id=1
    Session info: {'session_id': 1, 'memory_mode': 'short_term', ...}
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_session() -> None:
    """Test desktop session initialization."""
    from src.interfaces.desktop_app.session_manager import DesktopSessionManager

    db_path = project_root / "data" / "app.db"

    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}")
        print("Run 'python scripts/init_db.py' first.")
        sys.exit(1)

    print("Testing desktop session initialization...")
    print(f"Database: {db_path}")

    manager = DesktopSessionManager(str(db_path))

    try:
        session_id = await manager.get_or_create_session()
        print(f"[OK] Desktop session initialized: session_id={session_id}")

        # Get session info
        info = await manager.get_session_info(session_id)
        print(f"Session info: {info}")

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_session())
