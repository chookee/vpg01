"""Application entry point."""

import logging
import sys

from src.infrastructure.config import get_settings
from src.infrastructure.logging import setup_logger


def main() -> int:
    """Main application entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    logger = None
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
        # Use existing logger or create fallback
        if logger is not None:
            logger.exception("Fatal error: %s", exc)
        else:
            # Fallback logger - minimal configuration
            logging.basicConfig(
                level=logging.ERROR,
                format="%(asctime)s | %(levelname)s | %(message)s",
                force=True,
            )
            logging.exception("Fatal error: %s", exc)

        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
