"""Application entry point."""

import sys

from src.infrastructure.config import get_settings
from src.infrastructure.logging import get_logger, setup_logger


def main() -> int:
    """Main application entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        settings = get_settings()
        logger = setup_logger(debug=settings.debug)

        logger.info("Hello, World!")
        logger.info("Application: %s", settings.app_name)
        logger.debug("Debug mode: %s", settings.debug)
        logger.info("LLM Provider: %s", settings.llm_provider)

        if settings.is_bot_configured():
            logger.info("Telegram bot: configured")
        else:
            logger.warning("Telegram bot: not configured (set TELEGRAM_BOT_TOKEN)")

        return 0

    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
