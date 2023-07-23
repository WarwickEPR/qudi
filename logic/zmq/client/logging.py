# -*- coding: utf-8 -*-

import logging
import logging.handlers
import os
import sys
from ipywidgets.widgets import Output
from IPython.display import display, HTML
import IPython

log_format = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

# take the basics for setting up logging from Qudi core logging module


# Partially from https://ipywidgets.readthedocs.io/en/7.6.5/examples/Output%20Widget.html
class ConsoleHandler(logging.Handler):
    """ Custom logging handler sending logs to an output widget """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = {
            'width': '100%',
            'height': '200px',
        }
        style = {
            'font_size': '8px',
            'wrap-around': 'pre'
        }
        self.out = Output(layout=layout, style=style)
        with self.out:
            display(HTML('<style>span.log.DEBUG { color: blue; }</style>'))

    def emit(self, record):

        with self.out:
            display(HTML('<span class="log.{}">{}</span>'.format(record.levelname, self.format(record))))


class RejectionFilter(logging.Filter):

    def __init__(self, rejects: list):
        super().__init__()
        self.rejects = rejects

    def filter(self, record):
        for p in self.rejects:
            if record.name.startswith(p):
                return False
        return True


def initialize_logger(path='', name='qudi-client', suffix=None):
    """sets up the logger including a console, file and qt handler
    """
    # get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # add file log handler - should clear out existing stream logger e.g. to stderr
    os.makedirs('logs', mode=775, exist_ok=True)
    if suffix:
        logfile_path = os.path.join(path, 'logs/{}_{}.log'.format(name, suffix))
    else:
        logfile_path = os.path.join(path, 'logs/{}.log'.format(name))

    filelog = logging.FileHandler(filename=logfile_path)
    filelog.setFormatter(log_format)
    filelog.setLevel(logging.DEBUG)
    filelog.addFilter(RejectionFilter(['Comm', 'papermill', 'blib', 'matplotlib.font_manager']))
    logger.addHandler(filelog)
    logging.getLogger().info('Starting log ')


def add_console_logger():
    logger = logging.getLogger()
    handler = ConsoleHandler()
    handler.setFormatter(log_format)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(RejectionFilter(['Comm', 'papermill', 'blib', 'matplotlib.font_manager']))
    logger.addHandler(handler)
    return handler.out
