"""Desktop application entry point.

This module provides the entry point for the PyQt6 desktop application
with qasync for async/await support.

Usage:
    python -m src.interfaces.desktop_app.main

Requirements:
    - PyQt6>=6.6.0
    - qasync>=0.27.1
"""

import sys

from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from src.interfaces.desktop_app.main_window import MainWindow


def main() -> int:
    """Run the desktop application.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Create QApplication instance
        app = QApplication(sys.argv)
        app.setApplicationName("VPg01 Desktop")
        app.setOrganizationName("ZeroCode")

        # Create qasync event loop for async/await support
        loop = QEventLoop(app)
        with loop:
            # Create and show main window
            window = MainWindow()
            window.show()

            # Run event loop
            loop.run_forever()

        return 0

    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
