import logging
from typing import *


def configure_logging(level: str | Any = "DEBUG") -> None:
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler("obllmov.log", mode='w')
        ]

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

configure_logging()

logger = logging.getLogger(__name__)
