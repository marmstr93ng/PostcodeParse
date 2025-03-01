import logging
import re
from logging import LogRecord

from _constants import SystemDefs


def create_logger(file_append: bool = False) -> logging.Logger:
    """Create the logger with file and console handlers."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    remove_color_filter = _RemoveColorFilter()

    file_mode = "a" if file_append else "w"
    file_handler = logging.FileHandler(SystemDefs.LOGGING_FILE_PATH, file_mode, "utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)8s] --- (%(filename)15s:%(lineno)4s) %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.addFilter(remove_color_filter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(remove_color_filter)
    logger.addHandler(console_handler)

    return logger


class _RemoveColorFilter(logging.Filter):
    def filter(self, record: LogRecord) -> bool:
        """Remove the appended colour bytes."""
        ansi_re = re.compile(r"\x1b\[[0-9;]*m")
        if record and record.msg and isinstance(record.msg, str):
            record.msg = ansi_re.sub("", record.msg)
        return True
