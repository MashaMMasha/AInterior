import logging
import sys
from pathlib import Path
from typing import *


def _get_log_filename():
    script = Path(sys.argv[0]).stem if sys.argv[0] else "obllomov"
    return f"obllomov-{script}.log"


logger = logging.getLogger("obllomov")

_console_handler = logging.StreamHandler()
_file_handler = logging.FileHandler(_get_log_filename(), mode="w")
_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(filename)s:%(funcName)s - %(message)s")

_console_handler.setFormatter(_formatter)
_file_handler.setFormatter(_formatter)
_console_handler.setLevel(logging.INFO)
_file_handler.setLevel(logging.DEBUG)

logger.addHandler(_console_handler)
logger.addHandler(_file_handler)
logger.setLevel(logging.DEBUG)


def configure_logging(level: str | Any = "DEBUG") -> None:
    _file_handler.setLevel(level)
