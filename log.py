"""
Provide logger object.

Any other modules in "nonebot" should use "logger" from this module
to log messages.
"""

from loguru import logger


logger.remove()
# logger.add(sys.stdout, level="DEBUG", filter=debug_filter)
