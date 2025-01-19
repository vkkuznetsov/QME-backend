import logging
from datetime import datetime
from typing import Dict, Any

from pythonjsonlogger.json import JsonFormatter

from backend.project.config import Config


class CustomJsonFormatter(JsonFormatter):
    def add_fields(
            self,
            log_record: Dict[str, Any],
            record: logging.LogRecord,
            message_dict: Dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            log_record["timestamp"] = now
        if log_record.get("level"):
            log_record["level"] = log_record["level"].upper()
        else:
            log_record["level"] = record.levelname


def get_formatter(logging_config: Config) -> logging.Formatter:
    return CustomJsonFormatter(
        logging_config.logging_settings.LOGGING_FORMAT
    )
