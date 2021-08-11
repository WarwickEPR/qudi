# -*- coding: utf-8 -*-

import logging
import logging.handlers
import os


# take the basics for setting up logging from Qudi core logging module

def initialize_logger(path=''):
    """sets up the logger including a console, file and qt handler
    """
    # initialize logger
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    logging.addLevelName(logging.CRITICAL, 'critical')
    logging.addLevelName(logging.ERROR, 'error')
    logging.addLevelName(logging.WARNING, 'warning')
    logging.addLevelName(logging.INFO, 'info')
    logging.addLevelName(logging.DEBUG, 'debug')
    logging.addLevelName(logging.NOTSET, 'not set')
    logging.captureWarnings(True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # set level of stream handler which logs to stderr
    logger.handlers[0].setLevel(logging.INFO)

    # add file logger
    logfile_path = os.path.join(path, 'qudi-client.log')
    rotating_file_handler = logging.handlers.RotatingFileHandler(
        logfile_path, maxBytes=10*1024*1024, backupCount=5)
    rotating_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt="%Y-%m-%d %H:%M:%S"))
    rotating_file_handler.doRollover()
    rotating_file_handler.setLevel(logging.DEBUG)
    logger.addHandler(rotating_file_handler)

    for logger_name in ['core', 'client', 'broadcast']:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)
