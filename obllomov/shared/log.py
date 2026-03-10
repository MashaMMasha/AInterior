import logging
from .env import env


logging.basicConfig(
    level=env.LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('obllmov.log', mode='w'),
        logging.StreamHandler() 
    ]
)


logger = logging.getLogger(__name__)
