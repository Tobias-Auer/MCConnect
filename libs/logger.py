from ast import main
import logging
from os import name
import sys

def get_logger(name=None, log_level=logging.INFO, log_file='logs.log'):
    """
    Configure and return a logger instance.
    
    :param name: Name of the logger. Use None for the root logger.
    :param log_level: Logging level. Default is logging.INFO.
    :param log_file: File path for the log file. Default is 'logs.log'.
    :return: Configured logger instance.
    """
    log_file = "logs/" + log_file
    logger_var = logging.getLogger(name)
    logger_var.setLevel(log_level)

    if not logger_var.handlers:
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s', '%m-%d-%Y %H:%M:%S')
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(log_level)
        stdout_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)

        logger_var.addHandler(stdout_handler)
        logger_var.addHandler(file_handler)
    
    return logger_var

if __name__ == '__main__':
    logger = get_logger('loggingTest', logging.DEBUG)
    logger.debug('This is an debug message issued by logger.py to test logging functionality.')
