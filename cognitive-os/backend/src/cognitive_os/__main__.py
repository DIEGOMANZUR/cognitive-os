from __future__ import annotations

import structlog

BOOTSTRAP_MESSAGE = "Cognitive OS bootstrap OK"
logger = structlog.get_logger()


def main() -> None:
    """Run the minimal Cognitive OS bootstrap entrypoint."""
    logger.info(BOOTSTRAP_MESSAGE)


if __name__ == "__main__":
    main()
