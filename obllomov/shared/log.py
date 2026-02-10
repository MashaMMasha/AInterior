import logging
import os

log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()

logger = logging.getLogger(__name__)

logger.setLevel(getattr(logging, log_level))

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('obllomov.log', mode='w')
file_handler.setLevel(getattr(logging, log_level))
file_handler.setFormatter(formatter)


console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)


logger.addHandler(file_handler)
logger.addHandler(console_handler)
