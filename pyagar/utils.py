"""
``pyagar.utils``

Non categorized stuff.

"""
# pylint: disable=I0011,R0903
import asyncio

from pyagar.log import logger


@asyncio.coroutine
def hub(src, *dsts):
    """Broadcasts msgs from ``src.messages`` to all ``dsts.messages``."""
    src_q = src.messages
    dst_qs = [d.messages for d in dsts]
    while True:
        data = yield from src_q.get()
        for queue in dst_qs:
            queue.put_nowait(data)


class Output:
    """Prints every message received."""
    def __init__(self):
        self.messages = asyncio.Queue()

    @asyncio.coroutine
    def run(self):
        """Logs all everything."""
        while True:
            data = yield from self.messages.get()
            logger.debug(data)


def print_regions(regions):
    """Prints a pretty table with the region data."""
    from tabulate import tabulate
    headers = ["Region", "numServers", "numRealms", "numPlayers"]
    table = [[k, v["numServers"], v["numRealms"], v["numPlayers"]]
             for k, v in sorted(regions.items())]
    print(tabulate(table, headers, tablefmt="rst"))
