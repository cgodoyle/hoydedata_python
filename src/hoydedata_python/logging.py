import logging
import sys

from loguru import logger

from .config import settings

LEVEL = settings.LOG_LEVEL.upper()

logging.getLogger("pyogrio").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

logger.remove()

logger.add(
    sys.stderr,
    level=LEVEL,
    format="{time:HH:mm:ss} | <level>{level}</level> | {message} [{module}:{line}]",
    colorize=True,
)


def get_module_logger(module_name):
    """
    Get a logger for a specific module, with the module name included in the log messages.
    Args:
        module_name (str): The name of the module for which to get the logger.
    Returns:
        logger: A logger instance that includes the module name in log messages.
    """
    return logger.bind(module=module_name)
