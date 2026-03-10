import logging
# import os
# from .env import env


logging.basicConfig(
    # level=env.LOG_LEVEL,
    
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('obllmov.log', mode='w'),
        logging.StreamHandler() 
    ]
)


logger = logging.getLogger(__name__)
