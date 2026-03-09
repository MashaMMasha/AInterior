import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('obllmov.log', mode='w'),
        logging.StreamHandler() 
    ]
)


logger = logging.getLogger(__name__)
