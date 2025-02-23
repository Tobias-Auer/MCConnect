import logging
import sys
from logging.handlers import RotatingFileHandler

def get_logger(name=None, log_level=logging.DEBUG, log_file='logs.log', max_bytes=1000*1024, backup_count=20):
    """
    Configure and return a logger instance.
    
    :param name: Name of the logger. Use None for the root logger.
    :param log_level: Logging level for the console output. Default is logging.INFO.
    :param log_file: File path for the log file. Default is 'logs.log'.
    :param max_bytes: Maximum file size in bytes before rotating. Default is 500 KB for approximately 5000 lines.
    :param backup_count: Number of backup files to keep. Default is 5.
    :return: Configured logger instance.
    """
    log_file = "logs/" + log_file
    logger_var = logging.getLogger(name)
    logger_var.setLevel(logging.DEBUG)  

    if not logger_var.handlers:
        formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s', '%m-%d-%Y %H:%M:%S')
        
        # Console handler with variable log level
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(log_level)
        stdout_handler.setFormatter(formatter)

        file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
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
