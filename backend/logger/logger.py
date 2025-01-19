import logging

from backend.logger.formatter import get_formatter
from backend.project.config import get_config


def init_logging(log_level: str) -> logging.Logger:
    logger = logging.getLogger()
    log_handler = logging.StreamHandler()
    log_handler.setFormatter(get_formatter(get_config()))
    logger.addHandler(log_handler)
    logger.setLevel(log_level)
    return logger
