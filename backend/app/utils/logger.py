"""Lightweight centralized logging helpers for backend modules."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a module logger and ensure the root logger has a basic config."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    return logging.getLogger(name)
