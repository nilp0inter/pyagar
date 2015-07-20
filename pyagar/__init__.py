"""
``pyagar``
==========

This contains some shared constants.

"""
# pylint: disable=I0011,E1101
import asyncio
import pkg_resources

LOOP = asyncio.get_event_loop()
NICK = "pyagar"
try:
    VERSION = pkg_resources.get_distribution("pyagar").version
except pkg_resources.DistributionNotFound:
    VERSION = 'Unknown'
