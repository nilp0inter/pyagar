"""
``pyagar.log``

Contains the logger.

"""
# pylint: disable=I0011,C0103
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('pyagar')
