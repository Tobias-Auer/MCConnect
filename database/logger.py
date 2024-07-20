import logging
import sys

def get_logger(name=None, log_level=logging.INFO, log_file='logs.log'):
    """
    Configure and return a logger instance.
    
    :param name: Name of the logger. Use None for the root logger.
    :param log_level: Logging level for the console output. Default is logging.INFO.
    :param log_file: File path for the log file. Default is 'logs.log'.
    :return: Configured logger instance.
    """
    log_file = "logs/" + log_file
    logger_var = logging.getLogger(name)
    logger_var.setLevel(logging.DEBUG)  # Set to DEBUG to ensure the file handler always captures all levels

    if not logger_var.handlers:
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s', '%m-%d-%Y %H:%M:%S')
        
        # Console handler with variable log level
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(log_level)
        stdout_handler.setFormatter(formatter)

        # File handler with always DEBUG level
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        logger_var.addHandler(stdout_handler)
        logger_var.addHandler(file_handler)
    
    return logger_var

if __name__ == '__main__':
    logger = get_logger('loggingTest')
    logger.debug('This is a debug message issued by logger.py to test logging functionality.')
    logger.info('This is an info message issued by logger.py to test logging functionality.')
    logger.warning('This is a warning message issued by logger.py to test logging functionality.')
    logger.error('This is an error message issued by logger.py to test logging functionality.')
    logger.critical('This is a critical message issued by logger.py to test logging functionality.')
